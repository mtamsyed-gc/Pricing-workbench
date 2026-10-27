"""Pricing Workbench core package (SPEC.md is the source of truth)."""
from pathlib import Path

__version__ = "0.0.7"   # scheme: docs/INSTALL.md (owner, 25 Oct 2026)

PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parent


class PWError(Exception):
    """Base class for workbench errors."""


class MappingRequired(PWError):
    """A source value has no mapping (SPEC §2). Carries the unmapped items."""

    def __init__(self, message, items=None):
        super().__init__(message)
        self.items = list(items or [])


class ProposalRequired(PWError):
    """A rule or parameter needed for pricing is missing (CLAUDE.md): never default silently."""


class SpecError(PWError):
    """A catalogue spec or template spec is invalid."""


class GateFailed(PWError):
    """A validation gate stopped the run (SPEC §5, §6)."""

    def __init__(self, gate, message, details=None):
        super().__init__(f"{gate}: {message}")
        self.gate = gate
        self.details = details
