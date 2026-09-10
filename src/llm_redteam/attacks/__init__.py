"""Attack strategies: single-turn, crescendo, PAIR, TAP and genetic search."""

from llm_redteam.attacks.base import Attack
from llm_redteam.attacks.crescendo import CrescendoAttack
from llm_redteam.attacks.genetic import GeneticAttack
from llm_redteam.attacks.pair import PAIRAttack
from llm_redteam.attacks.single_turn import SingleTurnAttack
from llm_redteam.attacks.tap import TAPAttack

__all__ = [
    "Attack",
    "CrescendoAttack",
    "GeneticAttack",
    "PAIRAttack",
    "SingleTurnAttack",
    "TAPAttack",
]
