"""Exception hierarchy for LRTK.

All errors raised intentionally by LRTK inherit from :class:`LRTKError`,
so callers can catch the whole family with a single ``except`` clause.
"""

from __future__ import annotations


class LRTKError(Exception):
    """Base class for every error raised by LRTK."""


class ConfigError(LRTKError):
    """Raised when a configuration file or value is invalid."""


class RegistryError(LRTKError):
    """Raised when component registration or lookup fails."""


class PluginError(LRTKError):
    """Raised when an entry-point plugin cannot be loaded."""


class TargetError(LRTKError):
    """Raised when a target model cannot be reached or returns bad data."""


class ConverterError(LRTKError):
    """Raised when a prompt converter fails to transform a prompt."""


class ScorerError(LRTKError):
    """Raised when a scorer fails to evaluate a response."""


class AttackError(LRTKError):
    """Raised when an attack strategy cannot execute."""


class MemoryBackendError(LRTKError):
    """Raised when a memory backend cannot persist or read a run."""


class ReportError(LRTKError):
    """Raised when report generation fails."""
