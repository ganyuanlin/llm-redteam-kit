"""Tests for the component registry and entry-point plugin loading."""

from __future__ import annotations

from importlib import metadata

import pytest

from llm_redteam.exceptions import PluginError, RegistryError
from llm_redteam.registry import (
    KIND_TO_REGISTRY,
    Registry,
    list_components,
    load_plugins,
    plugins_loaded,
)


class _Widget:
    pass


class _OtherWidget(_Widget):
    pass


def test_registry_register_get_and_contains() -> None:
    registry: Registry[_Widget] = Registry("widget")
    registry.register("first", _Widget)
    assert "first" in registry
    assert registry.get("first") is _Widget
    assert registry.names() == ["first"]
    assert len(registry) == 1

    with pytest.raises(RegistryError, match="already registered"):
        registry.register("first", _OtherWidget)

    registry.register("first", _OtherWidget, override=True)
    assert registry.get("first") is _OtherWidget

    with pytest.raises(RegistryError, match="Unknown widget"):
        registry.get("missing")


def test_registry_decorator() -> None:
    registry: Registry[_Widget] = Registry("deco")
    decorated = registry.decorate("w")(_Widget)
    assert decorated is _Widget
    assert registry.names() == ["w"]


def test_builtin_registries_populated() -> None:
    components = list_components()
    assert set(components) == {
        "target",
        "converter",
        "attack",
        "scorer",
        "memory",
        "reporter",
    }
    assert "mock" in KIND_TO_REGISTRY["target"].names()
    assert "single_turn" in KIND_TO_REGISTRY["attack"].names()
    assert "json" in KIND_TO_REGISTRY["reporter"].names()


class _FakeEntryPoint:
    def __init__(self, name: str, value: object) -> None:
        self.name = name
        self._value = value

    def load(self) -> object:
        return self._value


def test_load_plugins_invokes_callables(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def register() -> None:
        calls.append("called")

    def fake_entry_points(*, group: str = "") -> list[_FakeEntryPoint]:
        return [
            _FakeEntryPoint("plugin-a", register),
            _FakeEntryPoint("plugin-b", "not-callable"),
        ]

    monkeypatch.setattr(metadata, "entry_points", fake_entry_points)
    loaded = load_plugins("fake.group")
    assert loaded == ["plugin-a", "plugin-b"]
    assert calls == ["called"]
    assert plugins_loaded() is True


def test_load_plugins_wraps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def register() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        metadata,
        "entry_points",
        lambda *, group="": [_FakeEntryPoint("bad", register)],
    )
    with pytest.raises(PluginError, match="Failed to load plugin"):
        load_plugins("fake.broken.group")
