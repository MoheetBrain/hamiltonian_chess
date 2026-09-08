"""``T_K`` — the truth kernel: a process-level driver for Lean 4 via ``lean_dojo_repl``.

What this module is, precisely: a ~line-protocol client for the ``lean_dojo_repl`` tactic that is
**already compiled** into a built mathlib4 checkout.  Sending ``{"sid": N, "cmd": "<tactic>"}`` on
stdin returns ``{"sid": M, "tacticState": "...", "error": null}``.  ``sid`` names a *saved* tactic
state inside the live Lean process, so an episode can revisit an earlier state and branch.

Facts this design is built on, all measured on the target machine
(``docs/VERIFIED_TRAJECTORY_ARENA_V0.md``):

* startup (import + elaborate the file prefix) costs **2.57–4.44 s, mean 3.24 s**; warm tactic
  steps run at **193 steps/s**.  Startup dominates, so a session is created once per episode and
  reused across every step — never restarted per step;
* ``{"sid":0,"cmd":"sorry"}`` is refused by the REPL itself with ``proof contains `sorry` ``;
* ``#print axioms`` separates a real proof (``[propext, Quot.sound]``) from a cheated one
  (``[sorryAx]``);
* the pretty-printed state is **scope-dependent** and therefore not a canonical form, so nothing
  here ever compares two state strings to decide whether a step was correct.  The single string
  comparison in this module is :func:`is_no_goals`, the backend's own unambiguous termination
  sentinel, and it is isolated in that one function so it can be audited by an AST scan.

Every failure path returns a typed :class:`StepResult`.  There is no silent skip and no silent
degradation: if the toolchain or the built oleans are missing, :func:`require_toolchain` raises
with the exact paths it looked at.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import IO, Any

from arena.canonical.schema import stable_hash
from arena.trajectory.schema import PPScope

# ---------------------------------------------------------------------------------------------
# Toolchain location
# ---------------------------------------------------------------------------------------------

#: The **built** 18 GB checkout: 5,680 ``.olean`` files, ``Mathlib.lean`` with 4,447 imports,
#: ``.lake/build/lib/Lean4Repl.olean`` present.  A second checkout of the same commit exists at
#: ``external/checkouts/mathlib4-29dcec0`` with 38 oleans and is **source only**; two prior audits
#: reached opposite conclusions by confusing them, so this path is named in full and recorded in
#: every trajectory.
DEFAULT_MATHLIB_ROOT = Path(
    "/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/"
    "leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
)
DEFAULT_ELAN_BIN = Path("/Users/moheet/.elan/bin")
#: Environment override so this package is usable on another machine with another build.
MATHLIB_ROOT_ENV = "HAMILTONIAN_MATHLIB_ROOT"
ELAN_BIN_ENV = "HAMILTONIAN_ELAN_BIN"

REPL_MARKER = "REPL> "


class ToolchainMissingError(RuntimeError):
    """The Lean toolchain or the built mathlib is absent.  Never degrade silently instead."""


@dataclass(frozen=True, slots=True)
class LeanToolchainConfig:
    """Everything needed to start a Lean process, plus the caller's cost caps."""

    mathlib_root: Path = DEFAULT_MATHLIB_ROOT
    lean_bin: Path = DEFAULT_ELAN_BIN / "lean"
    lake_bin: Path = DEFAULT_ELAN_BIN / "lake"
    #: Wall seconds allowed for import + prefix elaboration.  Measured mean 3.24 s, max 4.44 s.
    startup_timeout_s: float = 180.0
    #: Wall seconds allowed for one tactic.  Warm steps run at ~193/s; heavy automation is slower.
    step_timeout_s: float = 60.0
    #: Hard cap on one session's total lifetime.  Exceeding it expires the session, typed.
    session_lifetime_s: float = 900.0
    #: Wall seconds for the separate ``#print axioms`` re-elaboration of a finished script.
    kernel_timeout_s: float = 300.0
    max_heartbeats: int = 1_000_000

    @classmethod
    def from_env(cls, **overrides: Any) -> LeanToolchainConfig:
        """Read ``HAMILTONIAN_MATHLIB_ROOT`` / ``HAMILTONIAN_ELAN_BIN`` if set."""

        root = Path(os.environ.get(MATHLIB_ROOT_ENV, str(DEFAULT_MATHLIB_ROOT)))
        elan = Path(os.environ.get(ELAN_BIN_ENV, str(DEFAULT_ELAN_BIN)))
        base: dict[str, Any] = {
            "mathlib_root": root,
            "lean_bin": elan / "lean",
            "lake_bin": elan / "lake",
        }
        base.update(overrides)
        return cls(**base)


@dataclass(frozen=True, slots=True)
class ToolchainReport:
    """Result of looking for the toolchain.  ``available`` gates every Lean-dependent test."""

    available: bool
    mathlib_root: Path
    lean_bin: Path
    lake_bin: Path
    missing: tuple[str, ...] = ()
    lean_version_string: str = ""
    toolchain: str = ""

    def describe(self) -> str:
        if self.available:
            return (
                f"Lean toolchain OK: {self.lean_version_string} "
                f"toolchain={self.toolchain} mathlib_root={self.mathlib_root}"
            )
        return "Lean toolchain unavailable:\n  " + "\n  ".join(self.missing)


def check_toolchain(config: LeanToolchainConfig | None = None) -> ToolchainReport:
    """Look for the binaries, the checkout, and the built ``Lean4Repl.olean``.

    Returns a report rather than raising, so a test suite can skip cleanly on a machine without
    Lean.  Use :func:`require_toolchain` when absence should be a loud failure.
    """

    config = config or LeanToolchainConfig.from_env()
    missing: list[str] = []
    for label, path in (("lean binary", config.lean_bin), ("lake binary", config.lake_bin)):
        if not path.exists():
            missing.append(f"{label} not found at {path}")
    if not config.mathlib_root.is_dir():
        missing.append(f"mathlib checkout not found at {config.mathlib_root}")
    else:
        repl_olean = config.mathlib_root / ".lake" / "build" / "lib" / "Lean4Repl.olean"
        if not repl_olean.exists():
            missing.append(
                f"Lean4Repl.olean not built at {repl_olean} "
                "(the source-only checkout cannot run the REPL)"
            )
        mathlib_olean = config.mathlib_root / ".lake" / "build" / "lib" / "Mathlib.olean"
        if not mathlib_olean.exists():
            missing.append(
                f"Mathlib.olean not built at {mathlib_olean} "
                "(this checkout is source only; the built one is 18 GB with 5,680 oleans)"
            )
    if missing:
        return ToolchainReport(
            available=False,
            mathlib_root=config.mathlib_root,
            lean_bin=config.lean_bin,
            lake_bin=config.lake_bin,
            missing=tuple(missing),
        )
    toolchain_file = config.mathlib_root / "lean-toolchain"
    toolchain = (
        toolchain_file.read_text(encoding="utf-8").strip() if toolchain_file.exists() else ""
    )
    try:
        completed = subprocess.run(
            [str(config.lean_bin), "--version"],
            cwd=str(config.mathlib_root),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        version = completed.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - environment specific
        return ToolchainReport(
            available=False,
            mathlib_root=config.mathlib_root,
            lean_bin=config.lean_bin,
            lake_bin=config.lake_bin,
            missing=(f"could not run {config.lean_bin} --version: {exc}",),
        )
    return ToolchainReport(
        available=True,
        mathlib_root=config.mathlib_root,
        lean_bin=config.lean_bin,
        lake_bin=config.lake_bin,
        lean_version_string=version,
        toolchain=toolchain,
    )


def require_toolchain(config: LeanToolchainConfig | None = None) -> ToolchainReport:
    """Like :func:`check_toolchain` but raises with the exact paths that were checked."""

    report = check_toolchain(config)
    if not report.available:
        raise ToolchainMissingError(report.describe())
    return report


def count_oleans(config: LeanToolchainConfig | None = None) -> int:
    """Count every built ``.olean`` under ``.lake``.

    Recorded in each trajectory's ``formal_backend`` as the cheapest single number that says
    which of two same-commit checkouts was used: the built one reports 5,680 here and the
    source-only one reports 38.  Called once per bank build, never per episode.
    """

    config = config or LeanToolchainConfig.from_env()
    lake = config.mathlib_root / ".lake"
    if not lake.is_dir():
        return 0
    return sum(1 for _ in lake.rglob("*.olean"))


# ---------------------------------------------------------------------------------------------
# Tactic policy
# ---------------------------------------------------------------------------------------------

#: Tactic heads that can collapse a ten-step proof into one move.  Excluding them is how a caller
#: measures reasoning depth rather than a model's willingness to type ``aesop`` — but it changes
#: what the task means, so it is a **parameter with a recorded id**, never a hidden constant.
HEAVY_AUTOMATION: frozenset[str] = frozenset(
    {
        "aesop",
        "decide",
        "native_decide",
        "omega",
        "norm_num",
        "polyrith",
        "nlinarith",
        "linarith",
        "positivity",
        "simp_all",
        "simp?",
        "exact?",
        "apply?",
        "rw?",
        "hint",
        "tauto",
        "finish",
        "bound",
        "gcongr",
        "field_simp",
        "continuity",
        "measurability",
        "fun_prop",
        "norm_cast",
        "push_cast",
    }
)

#: Refused whatever the policy says.  ``sorry`` is the whole point of the exercise; the REPL also
#: refuses it, and this guard means a refusal is recorded even if a future backend does not.
ALWAYS_REFUSED: frozenset[str] = frozenset({"sorry", "sorryAx", "admit", "stop"})


class TacticDecision(StrEnum):
    ALLOWED = "ALLOWED"
    #: Blocked by the caller's configurable allow/deny list.
    DENIED_BY_POLICY = "DENIED_BY_POLICY"
    #: Blocked unconditionally: ``sorry`` and friends.
    REFUSED_UNSOUND = "REFUSED_UNSOUND"


@dataclass(frozen=True, slots=True)
class TacticPolicy:
    """What the caller will let a solver play, and under what name that choice is recorded.

    The **default records and restricts nothing** (``record_only``).  Restriction is opt-in via
    :meth:`no_heavy_automation` or an explicit allow-list, and whichever is chosen is stamped into
    every trajectory's provenance as :attr:`policy_id`.
    """

    name: str = "record_only"
    denied_heads: frozenset[str] = frozenset()
    #: ``None`` means "no allow-list"; a set means only those heads are legal.
    allowed_heads: frozenset[str] | None = None
    reject_multiline: bool = False

    @classmethod
    def record_only(cls) -> TacticPolicy:
        """Default: nothing is restricted, everything is counted."""

        return cls(name="record_only")

    @classmethod
    def no_heavy_automation(cls) -> TacticPolicy:
        """Ban the tactic families that outsource the search to mathlib's own automation."""

        return cls(name="no_heavy_automation", denied_heads=HEAVY_AUTOMATION)

    @property
    def policy_id(self) -> str:
        return stable_hash(
            {
                "name": self.name,
                "denied_heads": sorted(self.denied_heads),
                "allowed_heads": (
                    None if self.allowed_heads is None else sorted(self.allowed_heads)
                ),
                "reject_multiline": self.reject_multiline,
                "always_refused": sorted(ALWAYS_REFUSED),
            }
        )[:16]

    def head_of(self, tactic: str) -> str:
        stripped = tactic.strip()
        if not stripped:
            return ""
        head = stripped.split()[0]
        return head.rstrip(";").rstrip("[")

    def classify(self, tactic: str) -> tuple[TacticDecision, str]:
        """Return the decision and a human-readable reason (empty when allowed)."""

        head = self.head_of(tactic)
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_?!']*", tactic))
        unsound = tokens & ALWAYS_REFUSED
        if head in ALWAYS_REFUSED or unsound:
            return (
                TacticDecision.REFUSED_UNSOUND,
                f"tactic mentions unconditionally refused token(s) {sorted(unsound or {head})}",
            )
        if self.reject_multiline and "\n" in tactic.strip():
            return TacticDecision.DENIED_BY_POLICY, "multi-line tactic rejected by policy"
        if head in self.denied_heads:
            return TacticDecision.DENIED_BY_POLICY, f"tactic head {head!r} is on the deny-list"
        if self.allowed_heads is not None and head not in self.allowed_heads:
            return TacticDecision.DENIED_BY_POLICY, f"tactic head {head!r} is not on the allow-list"
        return TacticDecision.ALLOWED, ""


# ---------------------------------------------------------------------------------------------
# Probe construction
# ---------------------------------------------------------------------------------------------


class ProbeDiscardReason(StrEnum):
    """Why a candidate theorem could not become a probe.  Counted and reported (audit §7.7)."""

    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    DECL_OUT_OF_RANGE = "DECL_OUT_OF_RANGE"
    NO_BY_BLOCK = "NO_BY_BLOCK"
    NOT_THEOREM_OR_LEMMA = "NOT_THEOREM_OR_LEMMA"
    NO_TACTICS = "NO_TACTICS"
    MULTILINE_TACTIC = "MULTILINE_TACTIC"
    BELOW_MIN_HORIZON = "BELOW_MIN_HORIZON"
    ABOVE_MAX_HORIZON = "ABOVE_MAX_HORIZON"
    POLICY_BANNED_TACTIC = "POLICY_BANNED_TACTIC"
    LEAKS_TACTIC_IN_STATE = "LEAKS_TACTIC_IN_STATE"
    LEAKS_FULL_NAME_IN_STATE = "LEAKS_FULL_NAME_IN_STATE"


@dataclass(frozen=True, slots=True)
class LeanTheoremProbe:
    """A self-contained Lean file that opens a REPL on one theorem's initial goal.

    The file prefix stops **before** the declaration and the theorem is renamed ``probe_<name>``,
    so ``exact <its own name>`` cannot close the goal.  Measured: 29/30 probes built this way
    elaborated with the theorem out of scope.
    """

    problem_id: str
    full_name: str
    safe_name: str
    file_path: str
    statement: str
    prefix_text: str
    pp_scope: PPScope
    reference_tactics: tuple[str, ...]
    max_heartbeats: int = 1_000_000

    @property
    def probe_name(self) -> str:
        return f"probe_{self.safe_name}"

    def repl_source(self) -> str:
        """The file handed to ``lake env lean`` to open an interactive session."""

        return (
            "import Lean4Repl\n"
            + self.prefix_text
            + f"\n\nset_option maxHeartbeats {self.max_heartbeats} in\n"
            + self.statement
            + " := by\n  lean_dojo_repl\n  sorry\n"
        )

    def closed_script_source(self, tactics: Sequence[str]) -> str:
        """The finished proof plus ``#print axioms`` — the kernel check, a separate elaboration.

        The REPL probe always ends in ``sorry`` (that is how the file elaborates at all), so
        ``#print axioms`` inside the session would be meaningless.  Closure is therefore checked
        by re-elaborating the *whole* accepted script from scratch.
        """

        body = "\n".join(_indent_tactic(tactic) for tactic in tactics)
        return (
            self.prefix_text
            + f"\n\nset_option maxHeartbeats {self.max_heartbeats} in\n"
            + self.statement
            + " := by\n"
            + body
            + f"\n\n#print axioms {self.probe_name}\n"
        )


def _indent_tactic(tactic: str) -> str:
    lines = tactic.split("\n")
    return "\n".join("  " + line for line in lines)


_DECL_RE = re.compile(r"^(theorem|lemma)\s")
_NAME_RE = re.compile(r"^(theorem|lemma)\s+\S+")


def safe_lean_name(full_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", full_name)


def extract_pp_scope(prefix_lines: Sequence[str]) -> PPScope:
    """Best-effort reconstruction of the namespace/open scope the goal is printed under.

    Advisory metadata.  It exists because the same goal prints as ``univ`` under ``open Finset``
    and ``Finset.univ`` without it, so a reader comparing two ``pp`` strings needs to know which
    scope each was rendered in.  Nothing verifies against it.
    """

    namespaces: list[str] = []
    opens: list[str] = []
    for raw in prefix_lines:
        line = raw.strip()
        if line.startswith("namespace "):
            namespaces.append(line.removeprefix("namespace ").strip())
        elif line.startswith("end ") and namespaces:
            ending = line.removeprefix("end ").strip()
            if ending == namespaces[-1]:
                namespaces.pop()
        elif line.startswith("open ") and " in" not in line:
            opens.extend(line.removeprefix("open ").replace("scoped", "").split())
    return PPScope(
        current_namespace=".".join(namespaces),
        open_declarations=tuple(dict.fromkeys(opens)),
    )


def _trim_prefix(lines: list[str]) -> list[str]:
    """Drop trailing attributes, docstrings and ``... in`` modifiers that would bind our probe."""

    pre = list(lines)
    while pre and (
        pre[-1].strip() == ""
        or pre[-1].strip().startswith("@[")
        or pre[-1].rstrip().endswith(" in")
        or pre[-1].strip().startswith("/--")
        or pre[-1].strip().endswith("-/")
        or pre[-1].strip().startswith("--")
    ):
        if pre[-1].strip().endswith("-/"):
            while pre and not pre[-1].lstrip().startswith("/-"):
                pre.pop()
            if pre:
                pre.pop()
            continue
        pre.pop()
    return pre


@dataclass(frozen=True, slots=True)
class ProbeBuildResult:
    probe: LeanTheoremProbe | None
    discard_reason: ProbeDiscardReason | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.probe is not None


def build_probe(
    record: dict[str, Any],
    *,
    mathlib_root: Path,
    policy: TacticPolicy | None = None,
    min_reference_horizon: int = 1,
    max_reference_horizon: int | None = None,
    allow_multiline_tactics: bool = False,
    max_heartbeats: int = 1_000_000,
) -> ProbeBuildResult:
    """Turn one LeanDojo ``random/train.json`` record into a runnable probe, or say why not.

    Reads only these keys, all of which are the source's own: ``file_path``, ``full_name``,
    ``start``, ``end``, ``traced_tactics[].tactic``.
    """

    policy = policy or TacticPolicy.record_only()
    tactics = [step["tactic"] for step in (record.get("traced_tactics") or [])]
    if not tactics:
        return ProbeBuildResult(None, ProbeDiscardReason.NO_TACTICS)
    if len(tactics) < min_reference_horizon:
        return ProbeBuildResult(None, ProbeDiscardReason.BELOW_MIN_HORIZON, str(len(tactics)))
    if max_reference_horizon is not None and len(tactics) > max_reference_horizon:
        return ProbeBuildResult(None, ProbeDiscardReason.ABOVE_MAX_HORIZON, str(len(tactics)))
    if not allow_multiline_tactics and any("\n" in tactic for tactic in tactics):
        return ProbeBuildResult(None, ProbeDiscardReason.MULTILINE_TACTIC)
    for tactic in tactics:
        decision, reason = policy.classify(tactic)
        if decision is not TacticDecision.ALLOWED:
            return ProbeBuildResult(None, ProbeDiscardReason.POLICY_BANNED_TACTIC, reason)

    file_path = str(record["file_path"])
    source = mathlib_root / file_path
    if not source.exists():
        return ProbeBuildResult(None, ProbeDiscardReason.FILE_NOT_FOUND, str(source))
    lines = source.read_text(encoding="utf-8").split("\n")
    start_row, start_col = record["start"]
    end_row, end_col = record["end"]
    if start_row < 2 or end_row > len(lines):
        return ProbeBuildResult(
            None, ProbeDiscardReason.DECL_OUT_OF_RANGE, f"{start_row}..{end_row} of {len(lines)}"
        )
    decl_lines = lines[start_row - 1 : end_row]
    decl_lines[-1] = decl_lines[-1][:end_col]
    decl_lines[0] = decl_lines[0][start_col - 1 :]
    declaration = "\n".join(decl_lines)
    if ":= by" not in declaration:
        return ProbeBuildResult(None, ProbeDiscardReason.NO_BY_BLOCK)
    statement = declaration.split(":= by", 1)[0].rstrip()
    if not _DECL_RE.match(statement):
        return ProbeBuildResult(None, ProbeDiscardReason.NOT_THEOREM_OR_LEMMA)

    full_name = str(record["full_name"])
    safe = safe_lean_name(full_name)
    statement = _NAME_RE.sub(f"theorem probe_{safe}", statement, count=1)
    prefix_lines = _trim_prefix(lines[: start_row - 1])
    return ProbeBuildResult(
        LeanTheoremProbe(
            problem_id=f"{file_path}::{full_name}",
            full_name=full_name,
            safe_name=safe,
            file_path=file_path,
            statement=statement,
            prefix_text="\n".join(prefix_lines),
            pp_scope=extract_pp_scope(prefix_lines),
            reference_tactics=tuple(tactics),
            max_heartbeats=max_heartbeats,
        )
    )


# ---------------------------------------------------------------------------------------------
# Live session
# ---------------------------------------------------------------------------------------------


class StepOutcome(StrEnum):
    """Every way a step can end.  There is no ``None`` return and no silent skip."""

    OK = "OK"
    #: Lean's elaborator rejected the tactic and said why.
    TACTIC_ERROR = "TACTIC_ERROR"
    #: The caller's tactic policy refused it before it reached Lean.
    POLICY_REJECTED = "POLICY_REJECTED"
    #: ``sorry`` and friends, refused unconditionally.
    SORRY_REFUSED = "SORRY_REFUSED"
    TIMEOUT = "TIMEOUT"
    #: The Lean process exited, or emitted something unparseable.
    BACKEND_DEAD = "BACKEND_DEAD"
    #: The hard session-lifetime cap was hit.
    SESSION_EXPIRED = "SESSION_EXPIRED"
    #: The caller asked to act on a state id this session never produced.
    UNKNOWN_STATE_ID = "UNKNOWN_STATE_ID"


@dataclass(frozen=True, slots=True)
class StepResult:
    """A typed result for every attempt, successful or not."""

    outcome: StepOutcome
    tactic: str
    from_state_id: str
    to_state_id: str | None = None
    tactic_state: str | None = None
    error: str | None = None
    wall_ms: int = 0
    raw: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is StepOutcome.OK

    @property
    def closed(self) -> bool:
        """The backend says there is nothing left to prove *in this session*.

        Not the same as verified: closure is confirmed by re-elaborating the whole script and
        reading ``#print axioms`` — see :func:`verify_closed_script`.
        """

        return self.ok and self.tactic_state is not None and is_no_goals(self.tactic_state)


def is_no_goals(tactic_state: str) -> bool:
    """The backend's own termination sentinel.

    This is the **only** place in this package where a state string is compared against anything,
    and it compares against a fixed backend literal rather than against another state.  It was the
    terminal state in 40,594 of 40,683 fully-chained recorded proofs (99.8%).  It is a *necessary*
    condition for success, never a sufficient one: closure is decided by the kernel.
    """

    return tactic_state.strip() == "no goals"


@dataclass(frozen=True, slots=True)
class KernelVerification:
    """Result of re-elaborating the finished script and reading ``#print axioms``."""

    verified: bool
    print_axioms: str
    contains_sorry_ax: bool
    contains_of_reduce_bool: bool
    exit_code: int
    errors: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "print_axioms": self.print_axioms,
            "contains_sorry_ax": self.contains_sorry_ax,
            "contains_of_reduce_bool": self.contains_of_reduce_bool,
            "exit_code": self.exit_code,
            "errors": self.errors,
        }


class LeanReplSession:
    """One live Lean process holding one theorem's proof state.

    Startup costs ~3.2 s and steps cost ~5 ms, so the session is the unit that is reused: create
    it once per episode and drive many steps through it.  Use it as a context manager.
    """

    def __init__(
        self,
        probe: LeanTheoremProbe,
        *,
        config: LeanToolchainConfig | None = None,
        policy: TacticPolicy | None = None,
        workdir: Path | None = None,
    ) -> None:
        self.probe = probe
        self.config = config or LeanToolchainConfig.from_env()
        self.policy = policy or TacticPolicy.record_only()
        self._workdir = workdir
        self._owns_workdir = workdir is None
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_chunks: list[str] = []
        #: Non-protocol stdout, kept bounded.  Lean writes elaboration errors here, so an
        #: episode that never reaches the REPL banner still gets a real diagnostic instead of
        #: an unexplained timeout.
        self._stdout_tail: deque[str] = deque(maxlen=60)
        self._exited_early = False
        self._threads: list[threading.Thread] = []
        self._started_at = 0.0
        self._states: dict[str, str] = {}
        self._root_state_id: str | None = None
        self.step_log: list[StepResult] = []
        self.branch_log: list[str] = []
        self.startup_wall_s = 0.0

    # -- lifecycle ---------------------------------------------------------------

    def __enter__(self) -> LeanReplSession:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def root_state_id(self) -> str:
        if self._root_state_id is None:
            raise RuntimeError("session not started")
        return self._root_state_id

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def expired(self) -> bool:
        return bool(self._started_at) and (
            time.monotonic() - self._started_at > self.config.session_lifetime_s
        )

    def state_text(self, state_id: str) -> str | None:
        """The pretty-printed state the backend produced for this id, if this session made it."""

        return self._states.get(state_id)

    def known_state_ids(self) -> tuple[str, ...]:
        return tuple(self._states)

    def start(self) -> StepResult:
        """Launch Lean and read the root state.  Raises :class:`ToolchainMissingError` if absent."""

        require_toolchain(self.config)
        if self._workdir is None:
            self._workdir = Path(tempfile.mkdtemp(prefix="hamiltonian-lean-"))
        probe_file = self._workdir / f"{self.probe.probe_name[:80]}.lean"
        probe_file.write_text(self.probe.repl_source(), encoding="utf-8")
        started = time.monotonic()
        self._process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [str(self.config.lake_bin), "env", str(self.config.lean_bin), str(probe_file)],
            cwd=str(self.config.mathlib_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._started_at = started
        self._spawn_readers()
        response = self._read_response(self.config.startup_timeout_s)
        self.startup_wall_s = time.monotonic() - started
        if response is None:
            self.close()
            return StepResult(
                outcome=StepOutcome.BACKEND_DEAD,
                tactic="",
                from_state_id="",
                error=(
                    "the probe file never reached `lean_dojo_repl` "
                    f"(startup cap {self.config.startup_timeout_s}s): {self.diagnostics()}"
                ),
                wall_ms=int(self.startup_wall_s * 1000),
            )
        state_id = str(response.get("sid"))
        tactic_state = response.get("tacticState") or ""
        self._root_state_id = state_id
        self._states[state_id] = tactic_state
        return StepResult(
            outcome=StepOutcome.OK,
            tactic="",
            from_state_id="",
            to_state_id=state_id,
            tactic_state=tactic_state,
            wall_ms=int(self.startup_wall_s * 1000),
            raw=response,
        )

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            if process.poll() is None and process.stdin is not None:
                process.stdin.write("exit\n")
                process.stdin.flush()
        except (OSError, ValueError):  # pragma: no cover - process already gone
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover - only on a wedged Lean
            process.kill()
            process.wait(timeout=10)
        for thread in self._threads:
            thread.join(timeout=5)
        self._process = None
        if self._owns_workdir and self._workdir is not None:
            shutil.rmtree(self._workdir, ignore_errors=True)
            self._workdir = None

    def stderr_text(self) -> str:
        return "".join(self._stderr_chunks)

    def diagnostics(self) -> str:
        """Whatever Lean said that was not protocol traffic, plus how the process ended."""

        parts: list[str] = []
        if self._exited_early:
            code = self._process.poll() if self._process is not None else None
            parts.append(f"lean exited (returncode={code}) before answering")
        tail = "".join(self._stdout_tail).strip()
        if tail:
            parts.append(f"stdout tail: {tail[-2000:]}")
        stderr = self.stderr_text().strip()
        if stderr:
            parts.append(f"stderr: {stderr[-2000:]}")
        return "; ".join(parts) or "no output"

    # -- the transition function -------------------------------------------------

    def step(self, state_id: str, tactic: str) -> StepResult:
        """Apply ``tactic`` to the saved state ``state_id``.

        ``state_id`` may be *any* state this session has produced, including one from before a
        later step: that is how branching works, and re-entry is a supported operation rather
        than an accident.  Every rejection is a typed result and is appended to
        :attr:`step_log`, so a driver cannot quietly retry a failed episode into a success.
        """

        decision, reason = self.policy.classify(tactic)
        if decision is TacticDecision.REFUSED_UNSOUND:
            return self._log(StepResult(StepOutcome.SORRY_REFUSED, tactic, state_id, error=reason))
        if decision is TacticDecision.DENIED_BY_POLICY:
            return self._log(
                StepResult(StepOutcome.POLICY_REJECTED, tactic, state_id, error=reason)
            )
        if state_id not in self._states:
            return self._log(
                StepResult(
                    StepOutcome.UNKNOWN_STATE_ID,
                    tactic,
                    state_id,
                    error=(
                        f"state id {state_id!r} was not produced by this session; "
                        f"known ids: {self.known_state_ids()[:8]}..."
                    ),
                )
            )
        if self.expired:
            self.close()
            return self._log(
                StepResult(
                    StepOutcome.SESSION_EXPIRED,
                    tactic,
                    state_id,
                    error=f"session lifetime cap {self.config.session_lifetime_s}s exceeded",
                )
            )
        if not self.alive:
            return self._log(
                StepResult(
                    StepOutcome.BACKEND_DEAD,
                    tactic,
                    state_id,
                    error=f"lean process is not running: {self.diagnostics()}",
                )
            )

        started = time.monotonic()
        process = self._process
        assert process is not None and process.stdin is not None
        try:
            process.stdin.write(json.dumps({"sid": int(state_id), "cmd": tactic}) + "\n")
            process.stdin.flush()
        except (OSError, ValueError) as exc:
            return self._log(
                StepResult(
                    StepOutcome.BACKEND_DEAD,
                    tactic,
                    state_id,
                    error=f"could not write to lean stdin: {exc}",
                    wall_ms=int((time.monotonic() - started) * 1000),
                )
            )
        response = self._read_response(self.config.step_timeout_s)
        wall_ms = int((time.monotonic() - started) * 1000)
        if response is None:
            outcome = StepOutcome.TIMEOUT if self.alive else StepOutcome.BACKEND_DEAD
            self.close()
            return self._log(
                StepResult(
                    outcome,
                    tactic,
                    state_id,
                    error=(
                        f"no response within {self.config.step_timeout_s}s: {self.diagnostics()}"
                    ),
                    wall_ms=wall_ms,
                )
            )
        if response.get("error"):
            return self._log(
                StepResult(
                    StepOutcome.TACTIC_ERROR,
                    tactic,
                    state_id,
                    error=str(response["error"]),
                    wall_ms=wall_ms,
                    raw=response,
                )
            )
        new_id = str(response.get("sid"))
        tactic_state = response.get("tacticState") or ""
        self._states[new_id] = tactic_state
        return self._log(
            StepResult(
                StepOutcome.OK,
                tactic,
                state_id,
                to_state_id=new_id,
                tactic_state=tactic_state,
                wall_ms=wall_ms,
                raw=response,
            )
        )

    def branch(self, state_id: str) -> StepResult:
        """Re-enter an earlier saved state.

        The backend keeps every state it has produced, so this is a lookup plus an audit-trail
        entry, not a re-computation.  Returning here is legitimate search; returning here *to
        hide a rejected step* is the failure mode, which is why the branch and every rejection
        are both logged.
        """

        if state_id not in self._states:
            return StepResult(
                StepOutcome.UNKNOWN_STATE_ID,
                "",
                state_id,
                error=f"state id {state_id!r} was not produced by this session",
            )
        self.branch_log.append(state_id)
        return StepResult(
            StepOutcome.OK,
            "",
            state_id,
            to_state_id=state_id,
            tactic_state=self._states[state_id],
        )

    # -- plumbing ----------------------------------------------------------------

    def _log(self, result: StepResult) -> StepResult:
        self.step_log.append(result)
        return result

    def _spawn_readers(self) -> None:
        process = self._process
        assert process is not None

        def pump(stream: IO[str], sink: queue.Queue[str | None] | list[str]) -> None:
            try:
                for line in stream:
                    if isinstance(sink, list):
                        sink.append(line)
                    else:
                        sink.put(line)
            finally:
                if not isinstance(sink, list):
                    sink.put(None)

        assert process.stdout is not None and process.stderr is not None
        for stream, sink in (
            (process.stdout, self._stdout_queue),
            (process.stderr, self._stderr_chunks),
        ):
            thread = threading.Thread(target=pump, args=(stream, sink), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _read_response(self, timeout_s: float) -> dict[str, Any] | None:
        """Pull lines until a ``REPL> `` line arrives, or the deadline passes."""

        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                line = self._stdout_queue.get(timeout=remaining)
            except queue.Empty:
                return None
            if line is None:
                self._exited_early = True
                return None
            if not line.startswith(REPL_MARKER):
                self._stdout_tail.append(line)
                continue
            try:
                parsed = json.loads(line[len(REPL_MARKER) :])
            except json.JSONDecodeError:
                self._stdout_tail.append(line)
                return None
            return parsed if isinstance(parsed, dict) else None


# ---------------------------------------------------------------------------------------------
# Kernel-backed closure check
# ---------------------------------------------------------------------------------------------

_AXIOMS_RE = re.compile(r"^'(?P<name>[^']+)' depends on axioms: \[(?P<axioms>[^\]]*)\]", re.M)


def verify_closed_script(
    probe: LeanTheoremProbe,
    tactics: Sequence[str],
    *,
    config: LeanToolchainConfig | None = None,
    workdir: Path | None = None,
) -> KernelVerification:
    """Re-elaborate the accepted script from scratch and read ``#print axioms``.

    This is the closure authority.  ``no goals`` in the REPL says the tactic block finished; this
    says the resulting declaration type-checks and depends on no ``sorryAx``.  A proof closed by
    ``decide``/``native_decide`` shows ``Lean.ofReduceBool`` and is flagged rather than silently
    accepted.
    """

    config = config or LeanToolchainConfig.from_env()
    require_toolchain(config)
    owns = workdir is None
    directory = workdir or Path(tempfile.mkdtemp(prefix="hamiltonian-kernel-"))
    try:
        script = directory / f"{probe.probe_name[:80]}_closed.lean"
        script.write_text(probe.closed_script_source(tactics), encoding="utf-8")
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [str(config.lake_bin), "env", str(config.lean_bin), str(script)],
            cwd=str(config.mathlib_root),
            capture_output=True,
            text=True,
            timeout=config.kernel_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return KernelVerification(
            verified=False,
            print_axioms="",
            contains_sorry_ax=False,
            contains_of_reduce_bool=False,
            exit_code=-1,
            errors=f"kernel re-elaboration exceeded {config.kernel_timeout_s}s",
        )
    finally:
        if owns:
            shutil.rmtree(directory, ignore_errors=True)

    output = completed.stdout + completed.stderr
    match = None
    for candidate in _AXIOMS_RE.finditer(output):
        # Lean reports the fully qualified name, so a probe declared inside `namespace Foo`
        # prints as 'Foo.probe_...'.  Accept the qualified form, never a different declaration.
        name = candidate.group("name")
        if name == probe.probe_name or name.endswith(f".{probe.probe_name}"):
            match = candidate
            break
    errors = "\n".join(line for line in output.split("\n") if ": error:" in line)
    if match is None:
        return KernelVerification(
            verified=False,
            print_axioms="",
            contains_sorry_ax=False,
            contains_of_reduce_bool=False,
            exit_code=completed.returncode,
            errors=errors or output[-4000:],
        )
    axioms = [item.strip() for item in match.group("axioms").split(",") if item.strip()]
    has_sorry = any("sorryAx" in axiom for axiom in axioms)
    has_reduce_bool = any("ofReduceBool" in axiom for axiom in axioms)
    return KernelVerification(
        verified=(completed.returncode == 0 and not has_sorry and not errors),
        print_axioms=match.group(0),
        contains_sorry_ax=has_sorry,
        contains_of_reduce_bool=has_reduce_bool,
        exit_code=completed.returncode,
        errors=errors,
    )


# ---------------------------------------------------------------------------------------------
# Streaming reader for the 373 MB one-line problem bank
# ---------------------------------------------------------------------------------------------

#: The DEVELOPMENT split.  ``random/{val,test}.json`` and ``novel_premises/{val,test}.json`` are
#: SEALED by ``artifacts/manifests/SEALED_SPLITS.json`` and are never read by this package.
SEALED_SPLIT_PATHS = (
    "novel_premises/val.json",
    "novel_premises/test.json",
    "random/val.json",
    "random/test.json",
)


class SealedSplitError(RuntimeError):
    """Raised on any attempt to read a sealed promotion/eval split."""


def assert_not_sealed(path: Path) -> None:
    text = str(path).replace(os.sep, "/")
    for sealed in SEALED_SPLIT_PATHS:
        if text.endswith(sealed):
            raise SealedSplitError(
                f"{path} is a SEALED split (artifacts/manifests/SEALED_SPLITS.json). "
                "Only random/train.json may be read during development."
            )


def iter_leandojo_records(
    path: Path,
    *,
    limit: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream a LeanDojo split file that is one 373 MB JSON array on a single line.

    ``json.load`` on that file costs several gigabytes of resident memory; this yields one record
    at a time with a bounded buffer so a ``--limit 50`` scan stops early and costs nothing.
    """

    assert_not_sealed(path)
    decoder = json.JSONDecoder()
    buffer = ""
    emitted = 0
    with path.open("r", encoding="utf-8") as handle:
        # Skip to the opening bracket of the array.
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                return
            buffer += chunk
            stripped = buffer.lstrip()
            if stripped.startswith("["):
                buffer = stripped[1:]
                break
            if stripped:
                raise ValueError(f"{path} does not start with a JSON array")
        while True:
            buffer = buffer.lstrip()
            while buffer[:1] == ",":
                buffer = buffer[1:].lstrip()
            if buffer[:1] == "]":
                return
            if not buffer:
                chunk = handle.read(1 << 20)
                if not chunk:
                    return
                buffer += chunk
                continue
            try:
                value, index = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = handle.read(1 << 20)
                if not chunk:
                    return
                buffer += chunk
                continue
            buffer = buffer[index:]
            if isinstance(value, dict):
                yield value
                emitted += 1
                if limit is not None and emitted >= limit:
                    return


@dataclass(slots=True)
class DiscardLedger:
    """Counts of every rejected candidate, by reason.  Reported with every bank (audit §7.7)."""

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, reason: str | ProbeDiscardReason, times: int = 1) -> None:
        key = reason.value if isinstance(reason, ProbeDiscardReason) else str(reason)
        self.counts[key] = self.counts.get(key, 0) + times

    def merge(self, other: DiscardLedger) -> None:
        for key, value in other.counts.items():
            self.record(key, value)

    def total(self) -> int:
        return sum(self.counts.values())

    def to_dict(self) -> dict[str, int]:
        return dict(sorted(self.counts.items()))


def summarise_tactic_heads(tactics: Iterable[str], policy: TacticPolicy) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tactic in tactics:
        head = policy.head_of(tactic)
        counts[head] = counts.get(head, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
