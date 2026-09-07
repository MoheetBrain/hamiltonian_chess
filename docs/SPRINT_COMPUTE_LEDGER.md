# 72-Hour Sprint — Compute Ledger

Every instance start/stop, its purpose, and approximate CPU/GPU hours. Idle instances are stopped.

## Inventory taken at sprint hour 0

```
gcloud compute instances list
NAME     ZONE            MACHINE_TYPE    STATUS
a100-40  us-central1-b   a2-highgpu-1g   TERMINATED
h3       europe-west4-b  h3-standard-88  TERMINATED
a100     europe-west4-a  a2-ultragpu-1g  TERMINATED
```

Account `abdulmoheetahmed@gmail.com`, project `project-08679972-d14a-4025-94f`.
Accelerators available in `europe-west4-c`: H100 80GB, H100 MEGA, L4, RTX PRO 6000, T4, V100, P4.

**Local:** Apple M5 Max, 40 cores, 48 GB. Ollama 0.33.2 serving `qwen38-rvn:latest`
(ID `25eb57cb8173`, 16 GB, Q4_K_M) and `gemma4:12b` (`4eb23ef187e2`).
**No `torch` is installed in the shared venv or system Python**, and the local machine is Apple
Silicon (MPS, no CUDA) — so any fine-tuning requires a cloud GPU and an environment build.

## Allocation decision, and why

| Workload | Where | Why not elsewhere |
|---|---|---|
| Task-family construction from LeanDojo (259,580 rows / 373 MB JSON) | **local CPU** | Streamed JSON parsing on 40 cores is not the bottleneck; shipping 373 MB to a cloud VM and paying for 88 vCPU would add wall-clock, not remove it |
| Model-free shortcut baselines | **local CPU** | Seconds-to-minutes of scikit-free numpy/stdlib work |
| Game-R / V7 Solver inference | **local Ollama** | The 16 GB Q4_K_M model is already resident locally. Re-provisioning it on a cloud GPU costs a download plus setup for a workload that is latency-bound, not FLOP-bound, at ~20 s/call |
| Matched fine-tuning (if reached) | **GCP A100** | Genuinely impossible locally: no CUDA, no torch |

**No cloud instance has been started.** Starting an 88-vCPU or A100 box before there is a workload
that needs it would be pure cost with no wall-clock gain — the directive's "do not leave expensive
machines idle" cuts both ways. The A100 is started only if the sprint reaches matched learning.

## Ledger

| # | Instance | Start | Purpose | Workload | Stop | Approx hours |
|---|---|---|---|---|---|---|
| — | (no cloud instance started) | — | — | — | — | **0 GPU-h, 0 cloud CPU-h** |
| L1 | local Ollama (M5 Max) | 12:38:56 | Fitness V7 DEV | `fitness_v7 develop --solver qwen38-rvn`, 872 planned calls / 900 budget, bare condition, digest `25eb57cb8173…` verified before first call | running | ≈ 4.8 h wall-clock, single-threaded |
| L2 | local CPU (M5 Max, 40 cores) | 11:2x | task-family construction + model-free shortcut gates | 6 concurrent agents streaming 373 MB LeanDojo JSON, no model call | rolling | concurrent with L1, no contention |

**Local usage** is not billed and is not itemised here beyond the Solver run, which is the only
serialised resource: V7 is 392 calls at ≈ 20 s ≈ **2.2 h wall-clock**, single-threaded through
Ollama. All CPU agent work runs concurrently with it and does not contend, since the CPU agents
make no model call.
