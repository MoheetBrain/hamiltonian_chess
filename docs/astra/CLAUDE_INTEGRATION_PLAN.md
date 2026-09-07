# Claude integration plan

Astra found that Claude’s three real Lean families are capability-only: they expose pre-rendered Lean strings and do not use `CanonicalState` or `CanonicalAction`. The committed Formal Arena V1 spec already records this limitation. Astra found no existing canonical premise-selection bridge in the checked Claude worktree.

Astra built a research-only scoped envelope, deterministic train adapter, five parity codecs, an inventory checker, metamorphic tests, source pin/seal records, and a model-free shortcut audit. The bank contains 300 real development items from the first 5,000 `random/train.json` theorems: 240 development-training and 60 theorem-disjoint held-out items. All 1,800 candidates have complete admitted source headers, source-path provenance, import-closure and conservative declaration-order checks. There were zero kernel replays and zero recovered elaborated types.

What to cherry-pick from this branch:

```text
research/astra/game_r_premise/
research/astra/tests/
research/astra/artifacts/source_seal.json
research/astra/artifacts/development_manifest.json
research/astra/artifacts/coverage_report.json
research/astra/artifacts/parity_report.json
research/astra/artifacts/representation_coverage.json
research/astra/artifacts/shortcut_results.json
docs/astra/
```

Keep the adapter, envelope and codecs research-only until a future canonical schema and Lean-native assurance are approved. Do not merge the development bank into a hidden promotion set. Do not merge generated `.venv`, caches, Solver results, V7 files, `GOAL.md`, canonical world hashes or production canonical schema changes.

The next commands in a fresh checkout are:

```bash
git show --stat <astra-commit>
git worktree add /tmp/astra-review <astra-commit>
cd /tmp/astra-review
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD .venv/bin/python -m pytest research/astra/tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD .venv/bin/python -m research.astra.game_r_premise.audit
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD .venv/bin/python -m research.astra.game_r_premise.shortcut_audit --bank research/astra/artifacts/dev_bank.jsonl --out /tmp/astra-shortcuts.json
```

Before promotion, replace the historically exposed LeanDojo evaluation pools with a fresh externally controlled theorem/repository partition. Re-run the source pin, admission, parity, invariance and shortcut gates before exposing any model.

Decision tree:

* If V7 qualifies at least two mechanisms, Claude may compare its existing route with this stronger real-source Game-R route, keeping the scientific variables separate.
* If V7 qualifies zero or one mechanism, do not create another toy V8. Review and, if accepted, integrate the premise bridge as the next preregistered real Game-R instrument.
* If V7 is invalid, this bridge remains independently useful as a representation-parity prototype and a real task adapter.

Production files Claude may eventually modify are a future canonical-vNext adapter, a separately approved sealed-promotion loader and a preregistered experiment module. Production canonical-v0, verifier truth, Solver machinery and V7 artifacts should remain untouched in this integration.
