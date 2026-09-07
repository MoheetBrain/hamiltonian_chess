"""TRAINING_LANGUAGE_V0 (TL0) -- a small extensible core for machine-facing mathematics.

TL0 is ten record kinds plus libraries.  The core says how mathematical state, reasoning
actions, bindings, types, scope, evidence, obligations and state transitions are
represented; libraries add domain vocabulary as *data*.  See ``SPEC.md``.

The release's evidence level is ``TRAINING_LANGUAGE_V0_BASELINE``.  It is packaging and
interfaces, not a tournament result, and it makes no claim that any representation trains
better than any other.

Entry points::

    from releases.TRAINING_LANGUAGE_V0 import (
        DEFAULT_REGISTRY, State, acquisition_guide, parse_state, render_state, to_canonical,
    )
"""

from .acquisition import BANNED_TERMS, acquisition_guide, guide_hash, shared_sections
from .canonical_adapter import (
    CanonicalMapping,
    CanonicalMappingError,
    CompatibilityProfile,
    LossItem,
    LossKind,
    LossPolicy,
    LossReport,
    TL0Import,
    from_canonical,
    to_canonical,
)
from .core import (
    EVIDENCE_LEVEL,
    LANGUAGE_ID,
    LANGUAGE_VERSION,
    RESERVED_ATTRIBUTE_PREFIX,
    Action,
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Evidence,
    Extension,
    Goal,
    LibraryRef,
    Obligation,
    Scope,
    State,
    Status,
    StatusError,
    Term,
    TL0Error,
    Type,
)
from .hashes import compute_hashes, read_hashes, verify_hashes, write_hashes
from .human import show_state
from .libraries import (
    ALGEBRA_LIBRARY,
    CORE_LIBRARY,
    STANDARD_LIBRARIES,
    Library,
    OperationSpec,
    OperatorSpec,
    check_vocabulary,
)
from .parser import parse_state, parse_term, parse_type
from .renderer import LOSSLESS, PROMPT_VIEW, RenderConfig, render_state, render_term, render_type
from .surfaces import (
    DEFAULT_REGISTRY,
    DEFAULT_SURFACE_ID,
    CanonicalSurface,
    NativeSurface,
    Surface,
    SurfaceDescriptor,
    SurfaceError,
    SurfaceRegistry,
    build_default_registry,
    wrap_candidate,
    wrap_genome,
)
from .syntax import TL0SyntaxError
from .training_schema import (
    RECORD_SCHEMA_VERSION,
    Provenance,
    StateDelta,
    TrainingDataError,
    TrainingRecord,
    Transition,
    VerificationOutcome,
    action_envelope,
    parse_action,
    read_jsonl,
    render_action,
    write_jsonl,
)

__all__ = [
    "ALGEBRA_LIBRARY",
    "BANNED_TERMS",
    "CORE_LIBRARY",
    "DEFAULT_REGISTRY",
    "DEFAULT_SURFACE_ID",
    "EVIDENCE_LEVEL",
    "LANGUAGE_ID",
    "LANGUAGE_VERSION",
    "LOSSLESS",
    "PROMPT_VIEW",
    "RECORD_SCHEMA_VERSION",
    "RESERVED_ATTRIBUTE_PREFIX",
    "STANDARD_LIBRARIES",
    "Action",
    "CanonicalMapping",
    "CanonicalMappingError",
    "CanonicalSurface",
    "Claim",
    "ClaimRole",
    "CompatibilityProfile",
    "Decl",
    "DeclKind",
    "Evidence",
    "Extension",
    "Goal",
    "Library",
    "LibraryRef",
    "LossItem",
    "LossKind",
    "LossPolicy",
    "LossReport",
    "NativeSurface",
    "Obligation",
    "OperationSpec",
    "OperatorSpec",
    "Provenance",
    "RenderConfig",
    "StateDelta",
    "Scope",
    "State",
    "Status",
    "StatusError",
    "Surface",
    "SurfaceDescriptor",
    "SurfaceError",
    "SurfaceRegistry",
    "TL0Error",
    "TL0Import",
    "TL0SyntaxError",
    "Term",
    "TrainingDataError",
    "TrainingRecord",
    "Transition",
    "Type",
    "VerificationOutcome",
    "acquisition_guide",
    "action_envelope",
    "build_default_registry",
    "check_vocabulary",
    "compute_hashes",
    "from_canonical",
    "guide_hash",
    "parse_action",
    "parse_state",
    "parse_term",
    "parse_type",
    "read_hashes",
    "read_jsonl",
    "render_action",
    "render_state",
    "render_term",
    "render_type",
    "shared_sections",
    "show_state",
    "to_canonical",
    "verify_hashes",
    "wrap_candidate",
    "wrap_genome",
    "write_hashes",
    "write_jsonl",
]
