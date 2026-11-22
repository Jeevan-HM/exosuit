"""Generate and score structured intents without applying any proposed edits."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from intent_contract import decision_key, validate_plan
from training_utils import read_records


def score_answer(text, expected, context):
    try:
        actual = json.loads(text)
    except (ValueError, TypeError):
        return {"json_valid": False, "contract_valid": False, "decision_correct": False, "error": "Invalid JSON"}
    try:
        validate_plan(actual, context)
    except (ValueError, TypeError, KeyError) as error:
        return {"json_valid": True, "contract_valid": False, "decision_correct": False, "error": str(error)}
    correct = decision_key(actual) == decision_key(expected)
    return {"json_valid": True, "contract_valid": True, "decision_correct": correct, "error": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="microsoft/Phi-3-mini-4k-instruct")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".summary.json").exists():
        parser.error("Choose a new output path; evaluation results will not be overwritten.")
    if not 1 <= args.max_new_tokens <= 1024:
        parser.error("max-new-tokens must be between 1 and 1024.")
    records = read_records(args.data)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("limit must be positive.")
        records = records[:args.limit]
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftConfig, PeftModel
    if not torch.cuda.is_available():
        parser.error("Evaluation uses the NVIDIA GPU; no CUDA device is visible.")
    model_id, revision = args.model, args.revision
    if args.adapter:
        cfg = PeftConfig.from_pretrained(args.adapter)
        model_id = cfg.base_model_name_or_path
        revision = cfg.revision or args.revision
    tokenizer = AutoTokenizer.from_pretrained(args.adapter or model_id, **({} if args.adapter else {"revision": revision}), trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype=torch.bfloat16, attn_implementation="sdpa", trust_remote_code=False, use_safetensors=True)
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.to("cuda").eval()
    model.config.use_cache = True
    stops = {tokenizer.eos_token_id}
    if "<|end|>" in tokenizer.get_vocab():
        stops.add(tokenizer.convert_tokens_to_ids("<|end|>"))
    totals = defaultdict(int)
    by_kind = defaultdict(lambda: defaultdict(int))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in records:
            expected = json.loads(row["messages"][-1]["content"])
            validate_plan(expected, row["context"])
            inputs = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to("cuda")
            limit = getattr(model.config, "max_position_embeddings", 4096)
            if inputs["input_ids"].shape[-1] + args.max_new_tokens > limit:
                raise ValueError(f"{row['id']}: prompt plus requested answer exceeds the model context.")
            with torch.inference_mode():
                ids = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False, eos_token_id=sorted(s for s in stops if s is not None), pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            text = tokenizer.decode(ids[0, inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
            score = score_answer(text, expected, row["context"])
            output = {"id": row["id"], "kind": row.get("kind", "manual"), "synthetic": row.get("synthetic"), "request": row["messages"][-2]["content"], "expected": expected, "response": text, "score": score}
            handle.write(json.dumps(output)+"\n")
            handle.flush()
            totals["examples"] += 1
            by_kind[output["kind"]]["examples"] += 1
            for metric in ("json_valid", "contract_valid", "decision_correct"):
                totals[metric] += int(score[metric])
                by_kind[output["kind"]][metric] += int(score[metric])
            print(f"{totals['examples']}/{len(records)} {row['id']}: decision_correct={score['decision_correct']}")
    summary = {
        "base_model": model_id, "revision": getattr(model.config, "_commit_hash", None) or revision,
        "adapter": str(args.adapter) if args.adapter else None,
        "counts": dict(totals), "rates": {k: totals[k]/totals["examples"] for k in ("json_valid", "contract_valid", "decision_correct")},
        "by_kind": {key: dict(value) for key, value in by_kind.items()},
        "limitations": "Exact structured decision score, ignoring explanation/question wording. Synthetic sets measure only this generator's software tasks. Review the clinical intent and clarification wording separately. No hardware or patient validation.",
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
