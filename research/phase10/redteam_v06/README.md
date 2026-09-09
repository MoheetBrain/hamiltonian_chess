# HC-V0.6 red team

Independent attacks on the frozen HC-V0.6 assay, written and run **while the primary four-arm pass
was executing** and without reading its outcome distribution. Findings:
`docs/HC_V0_6_REDTEAM.md`. Raw output: `out/`.

Every attack is a standalone script that writes one JSON verdict into `out/` and prints a one-line
summary. Nothing here imports the live Lean or Ollama stack; the attacks are offline by
construction so that they can run while the assay owns the machine.

| script | attacks |
|---|---|
| `attack_01_branching.py` | can two arms at one anchor act on different Lean states |
| `attack_02_bijection.py` | a renderer that passes the bijection while showing more or less |
| `attack_03_leakage.py` | what the 6-character oracle floor lets through, over the whole bank |
| `attack_04_model_conditions.py` | is every controllable thing identical across arms and models |
| `attack_05_schedule.py` | is the arm order a pure, arm-independent function of (seed, anchor) |
| `attack_06_provenance.py` | forged cells, and prompt-hash re-derivation against the frozen bank |
| `attack_07_redraws.py` | is `k = 1` structural rather than conventional |
| `attack_08_clusters.py` | is the cluster unit the source file everywhere it matters |
| `attack_09_result_hash.py` | does the manifest hash move when the mathematics did not |
| `attack_10_control_exclusion.py` | can `R_ABLATED` read as a candidate language |
| `attack_11_calibration.py` | level of the clustered test, independent-arm null |
| `attack_11b_gates.py` | does the IU gate logic block, and does it match the frozen spec |
| `attack_11c_clustered_differences.py` | level when the paired differences themselves are clustered |
| `attack_12_endpoint.py` | score without mathematics; lose a genuine advance |
| `attack_13_report_driver.py` | the post-freeze analysis driver `hc_v0_6_report.py` |
| `attack_14_harness_failures.py` | is `ENVIRONMENT_ERROR` really never a mathematical zero |
| `attack_15_manifest_and_freeze.py` | manifest guarantees and freeze integrity |

Run one: `.venv/bin/python research/phase10/redteam_v06/attack_01_branching.py`

The two simulations take a few minutes each and accept
`[sims] [permutations] [bootstrap_resamples]` (defaults 400 / 2000 / 500).

`research/` is excluded from the repository's ruff gate. These files are nevertheless clean under
`ruff check` and `ruff format --check` with the exclusion overridden:

```
.venv/bin/python -m ruff check  research/phase10/redteam_v06 --config 'extend-exclude=[]'
.venv/bin/python -m ruff format --check research/phase10/redteam_v06 --config 'extend-exclude=[]'
```
