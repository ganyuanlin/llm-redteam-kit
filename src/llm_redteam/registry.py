"""Component registry with decorator-based and entry-point plugin support.

Every pluggable kind (targets, converters, attacks, scorers, memory backends
and reporters) owns a :class:`Registry`. Components register themselves at
import time with decorators such as ``@register_target("mock")``.
Third-party packages may additionally expose a no-argument callable under
the ``llm_redteam.plugins`` entry-point group.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any, Generic, TypeVar

from llm_redteam.exceptions import PluginError, RegistryError
from llm_redteam.logging import get_logger

T = TypeVar("T")
_LOG = get_logger(__name__)


class Registry(Generic[T]):
    """A name -> class mapping for one component kind."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._components: dict[str, type[T]] = {}

    def register(self, name: str, component: type[T], *, override: bool = False) -> type[T]:
        """Register ``component`` under ``name`` and return it.

        Re-registering the same name raises :class:`RegistryError` unless
        ``override`` is set, which supports test isolation and hot reload.
        """
        if name in self._components and not override:
            raise RegistryError(f"{self.kind} component {name!r} is already registered")
        self._components[name] = component
        return component

    def decorate(self, name: str, *, override: bool = False) -> Any:  # noqa: ANN401
        """Return a class decorator that registers the decorated class."""

        def _decorator(component: type[T]) -> type[T]:
            return self.register(name, component, override=override)

        return _decorator

    def get(self, name: str) -> type[T]:
        """Return the class registered under ``name``."""
        try:
            return self._components[name]
        except KeyError:
            available = ", ".join(sorted(self._components)) or "<none>"
            raise RegistryError(
                f"Unknown {self.kind} component {name!r}. Available: {available}"
            ) from None

    def names(self) -> list[str]:
        """Return all registered component names, sorted alphabetically."""
        return sorted(self._components)

    def __contains__(self, name: object) -> bool:
        return name in self._components

    def __len__(self) -> int:
        return len(self._components)


#: One registry per pluggable component kind.
targets: Registry[Any] = Registry("target")
converters: Registry[Any] = Registry("converter")
attacks: Registry[Any] = Registry("attack")
scorers: Registry[Any] = Registry("scorer")
memories: Registry[Any] = Registry("memory")
reporters: Registry[Any] = Registry("reporter")

KIND_TO_REGISTRY: dict[str, Registry[Any]] = {
    "target": targets,
    "converter": converters,
    "attack": attacks,
    "scorer": scorers,
    "memory": memories,
    "reporter": reporters,
}

# Decorator helpers --------------------------------------------------------


def register_target(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register a :class:`~llm_redteam.targets.base.Target` subclass."""
    return targets.decorate(name, override=override)


def register_converter(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register a :class:`~llm_redteam.converters.base.Converter` subclass."""
    return converters.decorate(name, override=override)


def register_attack(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register an :class:`~llm_redteam.attacks.base.Attack` subclass."""
    return attacks.decorate(name, override=override)


def register_scorer(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register a :class:`~llm_redteam.scorers.base.Scorer` subclass."""
    return scorers.decorate(name, override=override)


def register_memory(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register a :class:`~llm_redteam.memory.base.Memory` subclass."""
    return memories.decorate(name, override=override)


def register_reporter(name: str, *, override: bool = False) -> Any:  # noqa: ANN401
    """Register a :class:`~llm_redteam.reporting.base.Reporter` subclass."""
    return reporters.decorate(name, override=override)


# Entry-point plugins ------------------------------------------------------

_PLUGIN_GROUP = "llm_redteam.plugins"
_PLUGINS_LOADED = False


def load_plugins(group: str = _PLUGIN_GROUP) -> list[str]:
    """Discover and invoke entry-point plugins.

    Each entry point must resolve to a no-argument callable that performs
    registration as an import side effect. A broken plugin is reported and
    skipped so that one bad install cannot take down the whole CLI.
    """
    global _PLUGINS_LOADED
    loaded: list[str] = []
    for entry_point in metadata.entry_points(group=group):
        try:
            plugin = entry_point.load()
            if callable(plugin):
                plugin()
        except Exception as exc:  # pragma: no cover - defensive isolation
            raise PluginError(f"Failed to load plugin {entry_point.name!r}: {exc}") from exc
        loaded.append(entry_point.name)
        _LOG.info("Loaded plugin %s", entry_point.name)
    _PLUGINS_LOADED = True
    return loaded


def plugins_loaded() -> bool:
    """Return whether :func:`load_plugins` has run at least once."""
    return _PLUGINS_LOADED


def list_components() -> dict[str, list[str]]:
    """Return a JSON-serializable snapshot of every registry."""
    return {kind: registry.names() for kind, registry in KIND_TO_REGISTRY.items()}
