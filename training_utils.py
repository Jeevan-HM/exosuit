"""Dataset validation and answer-only token labels shared by training/tests."""

import hashlib
import json
from pathlib import Path


def read_records(path):
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("id") or not row.get("group_id"):
            raise ValueError(f"{path}:{line_number}: id and group_id are required.")
        messages = row.get("messages", [])
        if len(messages) < 2 or messages[-1].get("role") != "assistant" or messages[-2].get("role") != "user":
            raise ValueError(f"{row['id']}: expected a user request and final assistant answer.")
        if any(not isinstance(m.get("content"), str) or not m["content"].strip() for m in messages):
            raise ValueError(f"{row['id']}: empty or non-text message.")
        records.append(row)
    if not records:
        raise ValueError(f"Empty dataset: {path}")
    if len({r["id"] for r in records}) != len(records):
        raise ValueError(f"Duplicate example ids in {path}.")
    return records


def assert_disjoint(splits):
    """An annotation group must contain all paraphrases/derivatives of a case."""
    for index, (name, records) in enumerate(splits.items()):
        groups = {r["group_id"] for r in records}
        prompts = {json.dumps(r["messages"][:-1], sort_keys=True) for r in records}
        for other, other_records in list(splits.items())[index+1:]:
            if groups & {r["group_id"] for r in other_records}:
                raise ValueError(f"Annotation-group leakage between {name} and {other}.")
            if prompts & {json.dumps(r["messages"][:-1], sort_keys=True) for r in other_records}:
                raise ValueError(f"Duplicate prompts between {name} and {other}.")


def encode_answer(tokenizer, row, max_length):
    messages = row["messages"]
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    complete = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if complete[:len(prompt)] != prompt:
        raise ValueError(f"{row['id']}: chat-template prefix mismatch; answer masking would be incorrect.")
    if len(complete) > max_length:
        raise ValueError(f"{row['id']}: {len(complete)} tokens exceeds {max_length}; shorten the context or raise --max-length within model limits. Nothing was silently truncated.")
    if len(complete) <= len(prompt):
        raise ValueError(f"{row['id']}: no supervised answer tokens.")
    return {"input_ids": complete, "attention_mask": [1]*len(complete), "labels": [-100]*len(prompt)+complete[len(prompt):]}


class EncodedDataset:
    def __init__(self, tokenizer, records, max_length):
        self.rows = [encode_answer(tokenizer, row, max_length) for row in records]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
