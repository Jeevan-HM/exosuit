"""Single-GPU BF16 LoRA training for versioned exosuit intent proposals."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from training_utils import EncodedDataset, assert_disjoint, read_records, sha256

HERE = Path(__file__).resolve().parent
BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"


def preflight():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU is visible. Install a compatible NVIDIA driver and CUDA-enabled PyTorch in this environment.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("This recipe requires BF16 support.")
    # Exercise both forward and backward kernels instead of only checking a name.
    x = torch.randn(128, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
    loss = (x @ x.T).float().square().mean()
    loss.backward()
    attention = torch.randn(1, 4, 32, 32, device="cuda", dtype=torch.bfloat16, requires_grad=True)
    attention_loss = torch.nn.functional.scaled_dot_product_attention(attention, attention, attention).float().square().mean()
    attention_loss.backward()
    torch.cuda.synchronize()
    if not torch.isfinite(loss) or not torch.isfinite(x.grad).all() or not torch.isfinite(attention_loss) or not torch.isfinite(attention.grad).all():
        raise RuntimeError("CUDA BF16 forward/backward check was not finite.")
    result = {
        "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(), "capability": list(torch.cuda.get_device_capability()),
        "vram_gib": round(torch.cuda.get_device_properties(0).total_memory/1024**3, 1),
        "bf16_forward_backward": "passed",
        "sdpa_forward_backward": "passed",
    }
    del x, loss, attention, attention_loss
    torch.cuda.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE/"intent_data")
    parser.add_argument("--output", type=Path, default=HERE/"runs"/"intent-pilot")
    parser.add_argument("--model", default=BASE_MODEL)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        print(json.dumps(preflight(), indent=2))
        return
    if args.batch_size < 1 or args.gradient_accumulation < 1 or args.rank < 1 or args.epochs <= 0 or args.learning_rate <= 0:
        parser.error("Batch size, gradient accumulation, rank, epochs, and learning rate must be positive.")
    if not 128 <= args.max_length <= 4096:
        parser.error("Use a max length between 128 and 4096 for the default Phi-3 4K recipe.")
    if not args.validate_only and args.output.exists() and any(args.output.iterdir()):
        parser.error("Output directory is not empty. Pick a new --output for this experiment.")

    from transformers import AutoTokenizer, DataCollatorForSeq2Seq, EarlyStoppingCallback, Trainer, TrainingArguments, set_seed
    from intent_contract import validate_plan
    set_seed(args.seed)
    splits = {name: read_records(args.data/f"{name}.jsonl") for name in ("train", "validation", "test")}
    assert_disjoint(splits)
    for rows in splits.values():
        for row in rows:
            validate_plan(json.loads(row["messages"][-1]["content"]), row["context"])
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    datasets = {name: EncodedDataset(tokenizer, rows, args.max_length) for name, rows in splits.items()}
    summary = {name: {"examples": len(ds), "max_tokens": max(len(r["input_ids"]) for r in ds.rows)} for name, ds in datasets.items()}
    print(json.dumps(summary, indent=2))
    if args.validate_only:
        print("Dataset isolation, proposal labels, chat format, lengths, and answer masks passed. No model weights were loaded.")
        return

    gpu = preflight()
    import torch
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, TaskType, get_peft_model
    model = AutoModelForCausalLM.from_pretrained(
        args.model, revision=args.revision, dtype=torch.bfloat16,
        attn_implementation="sdpa", trust_remote_code=False, use_safetensors=True,
        low_cpu_mem_usage=True,
    )
    resolved_revision = getattr(model.config, "_commit_hash", None) or args.revision
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        r=args.rank, lora_alpha=args.rank*2, lora_dropout=0.05,
        target_modules="all-linear", bias="none", task_type=TaskType.CAUSAL_LM,
        revision=resolved_revision,
    ))
    model.print_trainable_parameters()
    args.output.mkdir(parents=True, exist_ok=True)
    run = {
        "purpose": "Therapist intent-to-proposal pilot; no live hardware execution.",
        "base_model": args.model, "resolved_revision": resolved_revision,
        "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "gpu": gpu, "datasets": summary,
        "data_sha256": {name: sha256(args.data/f"{name}.jsonl") for name in splits},
        "versions": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "accelerate", "tokenizers", "huggingface-hub", "safetensors")},
    }
    (args.output/"run_config.json").write_text(json.dumps(run, indent=2)+"\n", encoding="utf-8")
    (args.output/"data_manifest.json").write_text((args.data/"manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.output), num_train_epochs=args.epochs,
            max_steps=args.max_steps, learning_rate=args.learning_rate,
            per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size,
            gradient_accumulation_steps=args.gradient_accumulation,
            bf16=True, fp16=False, optim="adamw_torch", weight_decay=0.01,
            warmup_ratio=0.05, max_grad_norm=1.0,
            gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
            eval_strategy="epoch", save_strategy="epoch", save_total_limit=2,
            load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
            prediction_loss_only=True, logging_steps=10, report_to="none", push_to_hub=False,
            seed=args.seed, data_seed=args.seed, dataloader_num_workers=0,
        ),
        train_dataset=datasets["train"], eval_dataset=datasets["validation"],
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8),
        processing_class=tokenizer, callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )
    trainer.train()
    # Training selects on validation only. Test generation is an explicit later step.
    final = args.output/"adapter"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(final)
    (final/"run_config.json").write_text(json.dumps(run, indent=2)+"\n", encoding="utf-8")
    print(f"Saved adapter and tokenizer to {final}. Evaluate intent correctness; validation loss is not clinical validation.")


if __name__ == "__main__":
    main()
