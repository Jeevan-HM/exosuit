import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from build_intent_data import KINDS, build, demo_context, scenario
from evaluate import score_answer
from intent_contract import proposal, validate_plan
from training_utils import assert_disjoint, encode_answer, read_records


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.context = demo_context(random.Random(4), "tests", 1)
        self.request, self.plan = scenario("increase_extension", 0, self.context)

    def test_all_synthetic_targets_obey_contract(self):
        for kind in KINDS:
            for variant in range(5):
                context = demo_context(random.Random(variant), "tests", variant)
                _, answer = scenario(kind, variant, context)
                validate_plan(answer, context)

    def test_validator_never_mutates_device_state(self):
        before = copy.deepcopy(self.context)
        validate_plan(self.plan, self.context)
        self.assertEqual(self.context, before)

    def test_invalid_changes_are_rejected(self):
        for label, mutate in [
            ("stale", lambda p: p.update(state_version=p["state_version"]+1)),
            ("wrong session", lambda p: p.update(context_id="another patient")),
            ("unit", lambda p: p["changes"][0].update(unit="kPa")),
            ("bounds", lambda p: p["changes"][0].update(value=100)),
            ("delta", lambda p: p["changes"][0].update(value=self.context["parameters"]["extension_pressure"]["value"]+3)),
            ("nan", lambda p: p["changes"][0].update(value=float("nan"))),
            ("bool", lambda p: p["changes"][0].update(value=True)),
            ("duplicate", lambda p: p["changes"].append(copy.deepcopy(p["changes"][0]))),
            ("unknown field", lambda p: p.update(approved=True)),
            ("unknown parameter", lambda p: p["changes"][0].update(parameter="treadmill_speed")),
        ]:
            with self.subTest(label=label):
                plan = copy.deepcopy(self.plan)
                mutate(plan)
                with self.assertRaises(ValueError):
                    validate_plan(plan, self.context)

    def test_readonly_and_unconfigured_contract(self):
        context = copy.deepcopy(self.context)
        context["parameters"]["extension_pressure"]["writable"] = False
        with self.assertRaises(ValueError):
            validate_plan(self.plan, context)
        context = copy.deepcopy(self.context)
        context["environment"] = "unconfigured"
        with self.assertRaises(ValueError):
            validate_plan(self.plan, context)

    def test_edits_cannot_be_hidden_in_other_statuses(self):
        for status in ["clarify", "read_state", "pause_request", "unsupported"]:
            plan = copy.deepcopy(self.plan)
            plan["status"] = status
            plan["question"] = "Which amount?" if status == "clarify" else None
            with self.assertRaises(ValueError):
                validate_plan(plan, self.context)

    def test_timing_order_is_checked_on_complete_candidate(self):
        context = copy.deepcopy(self.context)
        context["parameters"]["tA_pct"].update(max=40, max_change=40)
        plan = proposal(context, "propose_update", [{"parameter": "tA_pct", "value": 35, "unit": "percent_gait_cycle"}])
        with self.assertRaises(ValueError):
            validate_plan(plan, context)

    def test_eval_rejects_wrong_but_in_range_target(self):
        other = copy.deepcopy(self.plan)
        other["changes"][0]["value"] += 1
        score = score_answer(json.dumps(other), self.plan, self.context)
        self.assertTrue(score["contract_valid"])
        self.assertFalse(score["decision_correct"])
        self.assertFalse(score_answer("not JSON", self.plan, self.context)["json_valid"])

    def test_generated_splits_and_duplicate_group_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build(root)
            splits = {name: read_records(root/f"{name}.jsonl") for name in result["splits"]}
            assert_disjoint(splits)
            self.assertEqual(len(splits["train"]), 800)
            leaked = copy.deepcopy(splits)
            leaked["validation"][0]["group_id"] = leaked["train"][0]["group_id"]
            with self.assertRaises(ValueError):
                assert_disjoint(leaked)


class TokenAndTrainingTests(unittest.TestCase):
    def tokenizer(self):
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-4k-instruct", trust_remote_code=False, local_files_only=True)

    def row(self):
        from intent_contract import messages_for
        context = demo_context(random.Random(1), "tokens", 1)
        request, answer = scenario("increase_extension", 0, context)
        return {"id": "tokens", "messages": messages_for(request, context)+[{"role": "assistant", "content": json.dumps(answer)}]}

    def test_real_phi3_answer_mask_and_length_failure(self):
        tok = self.tokenizer()
        row = self.row()
        encoded = encode_answer(tok, row, 2048)
        supervised = [value for value in encoded["labels"] if value != -100]
        text = tok.decode(supervised, skip_special_tokens=True)
        self.assertEqual(json.loads(text), json.loads(row["messages"][-1]["content"]))
        self.assertGreater(encoded["labels"].count(-100), 20)
        with self.assertRaises(ValueError):
            encode_answer(tok, row, 10)

    def test_multiturn_supervises_only_final_answer(self):
        tok = self.tokenizer()
        row = self.row()
        row["messages"][2:2] = [
            {"role": "assistant", "content": "Earlier proposal has not been applied."},
            {"role": "user", "content": "Cancel that. Increase extension pressure by 1 psi."},
        ]
        encoded = encode_answer(tok, row, 2048)
        text = tok.decode([t for t in encoded["labels"] if t != -100], skip_special_tokens=True)
        self.assertEqual(json.loads(text), json.loads(row["messages"][-1]["content"]))

    def test_actual_phi3_lora_training_and_adapter_reload(self):
        import torch
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model
        from transformers import Phi3Config, Phi3ForCausalLM, DataCollatorForSeq2Seq, Trainer, TrainingArguments
        from training_utils import EncodedDataset
        torch.set_num_threads(1)
        tok = self.tokenizer()
        config = Phi3Config(vocab_size=len(tok), hidden_size=64, intermediate_size=128,
                            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=4,
                            max_position_embeddings=2048, original_max_position_embeddings=2048,
                            pad_token_id=tok.pad_token_id, bos_token_id=tok.bos_token_id, eos_token_id=tok.eos_token_id)
        model = get_peft_model(Phi3ForCausalLM(config), LoraConfig(r=4, lora_alpha=8, target_modules="all-linear", task_type=TaskType.CAUSAL_LM))
        model.config.use_cache = False
        before = {key: val.detach().clone() for key, val in model.named_parameters() if val.requires_grad}
        rows = [self.row(), self.row()]
        dataset = EncodedDataset(tok, rows, 2048)
        with tempfile.TemporaryDirectory() as directory:
            trainer = Trainer(model=model, args=TrainingArguments(output_dir=directory, use_cpu=True, max_steps=1,
                per_device_train_batch_size=1, learning_rate=1e-3, report_to="none", save_strategy="no",
                gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
                dataloader_pin_memory=False, disable_tqdm=True), train_dataset=dataset,
                data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100), processing_class=tok)
            result = trainer.train()
            self.assertTrue(torch.isfinite(torch.tensor(result.training_loss)))
            self.assertTrue(any(not torch.equal(before[key], value) for key, value in model.named_parameters() if key in before))
            model.save_pretrained(directory)
            loaded = PeftModel.from_pretrained(Phi3ForCausalLM(config), directory)
            for key, val in model.named_parameters():
                if "lora_" in key:
                    self.assertTrue(torch.equal(val, dict(loaded.named_parameters())[key]))


if __name__ == "__main__":
    unittest.main()
