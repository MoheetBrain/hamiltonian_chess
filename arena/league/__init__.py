"""Multi-axis candidate league and Hall of Fame."""

from arena.league.hall_of_fame import HallOfFame, HallOfFameSuite
from arena.league.matches import LeagueMatch, MatchObservation
from arena.league.registry import CandidateRecord, LeagueRegistry, MultiAxisRegistry

__all__ = [
    "CandidateRecord",
    "HallOfFame",
    "HallOfFameSuite",
    "LeagueMatch",
    "LeagueRegistry",
    "MatchObservation",
    "MultiAxisRegistry",
]
