"""LLM Red Team Kit (LRTK).

A modular, reproducible framework for *authorized* LLM red-team testing.
Importing this package imports every built-in component module so that the
decorators in :mod:`llm_redteam.registry` run exactly once.
"""

from __future__ import annotations

__version__ = "1.0.0"

# Import component packages first so all decorators register themselves.
from llm_redteam import (  # noqa: E402
    attacks,
    converters,
    memory,
    reporting,
    scorers,
    targets,
)
from llm_redteam.converters.base import Converter  # noqa: E402
from llm_redteam.models import AttackContext  # noqa: E402
from llm_redteam.scorers.base import Scorer  # noqa: E402
from llm_redteam.targets.base import Target  # noqa: E402

# Resolve AttackContext's TYPE_CHECKING-only forward references now that the
# concrete component classes are imported.
AttackContext.model_rebuild(
    _types_namespace={"Converter": Converter, "Scorer": Scorer, "Target": Target}
)

from llm_redteam.exceptions import LRTKError  # noqa: E402
from llm_redteam.models import (  # noqa: E402
    AttackContext,
    AttackRun,
    Message,
    Prompt,
    Response,
    Score,
    TargetConfig,
    Turn,
)
from llm_redteam.orchestrator import Orchestrator  # noqa: E402
from llm_redteam.registry import (  # noqa: E402
    list_components,
    load_plugins,
)

__all__ = [
    "AttackContext",
    "AttackRun",
    "LRTKError",
    "Message",
    "Orchestrator",
    "Prompt",
    "Response",
    "Score",
    "TargetConfig",
    "Turn",
    "__version__",
    "attacks",
    "converters",
    "list_components",
    "load_plugins",
    "memory",
    "reporting",
    "scorers",
    "targets",
]
