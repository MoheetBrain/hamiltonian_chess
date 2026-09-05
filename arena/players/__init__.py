"""Strategic Arena roles. Verifiers remain physics, not strategic players."""

from .architect import Architect, ArchitectPlayer
from .refuter import Refuter
from .solver import OllamaSolver, SolverRequest, SolverResponse

__all__ = [
    "Architect",
    "ArchitectPlayer",
    "OllamaSolver",
    "Refuter",
    "SolverRequest",
    "SolverResponse",
]
