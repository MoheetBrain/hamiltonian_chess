#!/usr/bin/env python
"""Matched LoRA adaptation for NEXT_ACTION, run on one GPU under a hard wall-clock budget.

This is the explicit runner `matched_adaptation.py` delegates execution to. It exists to
answer one question: after genuinely matched short adaptation, is there a representation-
dependent behavioural signal, or is the fitness landscape flat?

Discipline this file enforces rather than assumes:

* every arm starts from the SAME base checkpoint, reloaded per arm, never from the previous
  arm's weights;
* every arm gets identical seed, optimizer, learning rate, LoRA configuration, update count,
  context length and evaluation items -- EXAMPLE_MATCHED;
* token counts are recorded per arm and never equalised silently, because example-matched and
  token-matched are different experiments and conflating them would be the whole result;
* successive halving uses a rule fixed in `HALVING_RULE` before any score is read;
* a hard deadline stops new work; whatever has completed is persisted.

    python gpu_matched_runner.py --data matched_next_action.json --deadline-minutes 40
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

#: Fixed BEFORE any score is observed. An arm is eliminated only if it trails the stage
#: leader by more than this margin; ties and near-ties are carried forward, because a 3pp
#: difference on 48 items is one flipped answer either way.
HALVING_RULE = {
    "stage_a": "all 5 arms; eliminate an arm only if it trails the stage leader by > 0.06 "
               "absolute on dev exact-match; otherwise carry it",
    "stage_b": "top 3 by dev exact-match (ties carried), larger matched budget",
    "stage_c": "top 2, fresh evaluation slice never used for selection",
    "minimum_margin": 0.06,
}

SYSTEM = (
    "You translate a machine-oriented mathematical state into the single next action.\n"
    "Reply with ONE JSON object and nothing else."
)


def build_prompt(tokenizer, input_text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": input_text + "\n\nNEXT ACTION (JSON):"}]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def canonical_json(text: str):
    """Parse a model completion into a comparable object, or None if it is not JSON."""

    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.split("\n", 1)[-1] if text[:4].isalpha() else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def score_prediction(prediction: str, target_text: str) -> dict[str, int]:
    """Exact canonical correctness, plus the two secondary quality signals."""

    parsed = canonical_json(prediction)
    target = json.loads(target_text)
    schema_valid = int(parsed is not None and isinstance(parsed, dict))
    # "Verifier-accepted" here means the action is well-formed for the oracle: it carries the
    # required keys with the right shapes. It is NOT a claim that the action is optimal.
    required = ("action_id", "operation", "arguments")
    verified = int(schema_valid and all(key in parsed for key in required))
    exact = int(parsed is not None and parsed == target)
    return {"exact": exact, "schema_valid": schema_valid, "verified": verified}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("gpu_sprint_results.json"))
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--deadline-minutes", type=float, default=40.0)
    parser.add_argument("--stage-a-examples", type=int, default=224)
    parser.add_argument("--stage-b-examples", type=int, default=576)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-len", type=int, default=1536)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--eval-batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    started = time.time()
    deadline = started + args.deadline_minutes * 60.0

    def remaining() -> float:
        return deadline - time.time()

    def elapsed() -> float:
        return time.time() - started

    import torch
    import transformers
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    provenance = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count(),
        "bf16_supported": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
    }
    try:
        import peft
        provenance["peft"] = peft.__version__
    except Exception:
        pass
    print("PROVENANCE", json.dumps(provenance), flush=True)
    if not torch.cuda.is_available():
        raise SystemExit("NO CUDA GPU VISIBLE — refusing to run (see GPU SAFETY)")

    payload = json.loads(args.data.read_text())
    arms: list[str] = list(payload["arms"])

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    print(f"loading base model {args.model} ({elapsed():.0f}s)", flush=True)
    base = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda:0")
    base_state = {k: v.detach().clone() for k, v in base.state_dict().items()}
    digest = None
    try:
        from huggingface_hub import model_info
        digest = model_info(args.model).sha
    except Exception:
        pass
    provenance["base_model"] = args.model
    provenance["base_model_revision"] = digest
    provenance["tokenizer"] = args.model
    print(f"base model ready ({elapsed():.0f}s), revision {digest}", flush=True)

    results: dict[str, dict] = {}

    def encode(example: dict) -> tuple[list[int], int]:
        prompt = build_prompt(tokenizer, example["input_text"])
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        target_ids = tokenizer(example["target_text"] + tokenizer.eos_token,
                               add_special_tokens=False)["input_ids"]
        ids = (prompt_ids + target_ids)[-args.max_len:]
        prompt_len = min(len(prompt_ids), max(0, len(ids) - 1))
        return ids, prompt_len

    def train_arm(arm: str, examples: list[dict], tag: str) -> dict:
        torch.manual_seed(args.seed)
        random.seed(args.seed)
        base.load_state_dict(base_state)  # identical starting checkpoint for every arm
        lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
                          task_type="CAUSAL_LM",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
        model = get_peft_model(base, lora)
        model.train()
        optimiser = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad], lr=args.lr)

        encoded = [encode(item) for item in examples]
        token_total = sum(len(ids) for ids, _ in encoded)
        losses: list[float] = []
        steps = 0
        for start in range(0, len(encoded), args.batch):
            if remaining() < 60:
                print(f"  [{arm}/{tag}] deadline guard: stopping training early", flush=True)
                break
            chunk = encoded[start:start + args.batch]
            width = max(len(ids) for ids, _ in chunk)
            pad = tokenizer.pad_token_id
            input_ids = torch.full((len(chunk), width), pad, dtype=torch.long)
            labels = torch.full((len(chunk), width), -100, dtype=torch.long)
            attention = torch.zeros((len(chunk), width), dtype=torch.long)
            for row, (ids, prompt_len) in enumerate(chunk):
                input_ids[row, : len(ids)] = torch.tensor(ids)
                attention[row, : len(ids)] = 1
                labels[row, prompt_len : len(ids)] = torch.tensor(ids[prompt_len:])
            out = model(input_ids=input_ids.cuda(), attention_mask=attention.cuda(),
                        labels=labels.cuda())
            out.loss.backward()
            optimiser.step()
            optimiser.zero_grad(set_to_none=True)
            losses.append(float(out.loss.detach()))
            steps += 1
        model.eval()
        return {"model": model, "steps": steps, "tokens": token_total,
                "loss_curve": [round(v, 4) for v in losses],
                "final_loss": round(sum(losses[-5:]) / max(1, len(losses[-5:])), 4)
                if losses else None}

    @torch.no_grad()
    def evaluate(model, examples: list[dict]) -> dict:
        per_item: list[dict] = []
        latencies: list[float] = []
        output_tokens: list[int] = []
        for start in range(0, len(examples), args.eval_batch):
            chunk = examples[start:start + args.eval_batch]
            prompts = [build_prompt(tokenizer, item["input_text"]) for item in chunk]
            batch = tokenizer(prompts, return_tensors="pt", padding=True,
                              truncation=True, max_length=args.max_len,
                              add_special_tokens=False).to("cuda")
            tick = time.time()
            generated = model.generate(**batch, max_new_tokens=192, do_sample=False,
                                       pad_token_id=tokenizer.pad_token_id)
            latencies.append((time.time() - tick) / len(chunk))
            for row, item in enumerate(chunk):
                new_tokens = generated[row][batch["input_ids"].shape[1]:]
                output_tokens.append(int((new_tokens != tokenizer.pad_token_id).sum()))
                text = tokenizer.decode(new_tokens, skip_special_tokens=True)
                per_item.append(score_prediction(text, item["target_text"]))
        n = len(per_item)
        return {
            "n": n,
            "exact": round(sum(x["exact"] for x in per_item) / n, 4),
            "schema_valid": round(sum(x["schema_valid"] for x in per_item) / n, 4),
            "verified": round(sum(x["verified"] for x in per_item) / n, 4),
            "per_item_exact": [x["exact"] for x in per_item],
            "mean_output_tokens": round(sum(output_tokens) / n, 1),
            "mean_latency_s": round(sum(latencies) / len(latencies), 3),
        }

    def persist() -> None:
        args.out.write_text(json.dumps({
            "provenance": provenance,
            "halving_rule": HALVING_RULE,
            "budget_mode": "EXAMPLE_MATCHED",
            "config": {"lr": args.lr, "seed": args.seed, "batch": args.batch,
                       "max_len": args.max_len, "optimizer": "AdamW",
                       "lora": {"r": 16, "alpha": 32, "dropout": 0.0,
                                "targets": ["q_proj", "k_proj", "v_proj", "o_proj"]}},
            "elapsed_seconds": round(elapsed(), 1),
            "results": results,
        }, indent=2))

    def run_stage(stage: str, active: list[str], count: int, split: str) -> None:
        for arm in active:
            if remaining() < 150:
                print(f"[{stage}] deadline: skipping {arm}", flush=True)
                continue
            examples = payload["splits"][arm]["train"][:count]
            trained = train_arm(arm, examples, stage)
            scores = evaluate(trained["model"], payload["splits"][arm][split])
            trained["model"].unload()
            del trained["model"]
            torch.cuda.empty_cache()
            record = results.setdefault(arm, {})
            record[stage] = {
                "train_examples": len(examples), "eval_split": split,
                "updates": trained["steps"], "train_tokens": trained["tokens"],
                "final_loss": trained["final_loss"], "loss_curve": trained["loss_curve"],
                **scores,
            }
            print(f"[{stage}] {arm:<24}exact {scores['exact']:.3f}  "
                  f"schema {scores['schema_valid']:.3f}  verified {scores['verified']:.3f}  "
                  f"tokens {trained['tokens']}  loss {trained['final_loss']}  "
                  f"({elapsed():.0f}s)", flush=True)
            persist()

    # ------------------------------------------------------------------------ Stage A
    print(f"\n=== STAGE A: {len(arms)} arms x {args.stage_a_examples} examples", flush=True)
    run_stage("stage_a", arms, args.stage_a_examples, "dev")

    scored = {a: results[a]["stage_a"]["exact"] for a in arms if a in results
              and "stage_a" in results[a]}
    if not scored:
        persist()
        raise SystemExit("no arm completed Stage A")
    leader = max(scored.values())
    survivors = [a for a, s in sorted(scored.items(), key=lambda kv: -kv[1])
                 if leader - s <= HALVING_RULE["minimum_margin"]][:3]
    if len(survivors) < 2:
        survivors = [a for a, _ in sorted(scored.items(), key=lambda kv: -kv[1])][:3]
    print(f"\nStage A leader {leader:.3f}; survivors {survivors}", flush=True)

    # ------------------------------------------------------------------------ Stage B
    if remaining() > 300:
        print(f"\n=== STAGE B: {len(survivors)} arms x {args.stage_b_examples} examples",
              flush=True)
        run_stage("stage_b", survivors, args.stage_b_examples, "dev")

    # ------------------------------------------------------------------------ Stage C
    b_scored = {a: results[a]["stage_b"]["exact"] for a in survivors
                if a in results and "stage_b" in results[a]}
    if b_scored and remaining() > 300:
        finalists = [a for a, _ in sorted(b_scored.items(), key=lambda kv: -kv[1])][:2]
        print(f"\n=== STAGE C: {finalists} on the fresh slice", flush=True)
        run_stage("stage_c", finalists, args.stage_b_examples, "fresh")

    persist()
    print(f"\nwrote {args.out} after {elapsed():.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
