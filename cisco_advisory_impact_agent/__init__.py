"""Cisco Advisory Impact Agent — AI-driven Cisco firewall advisory impact analysis.

Distributed as a uv tool; the on-PATH command is `caia`
(entry point: :func:`cisco_advisory_impact_agent.cli.main`).
"""

from __future__ import annotations

from cisco_advisory_impact_agent.version import read_installed_version

__all__ = ["__version__"]

__version__ = read_installed_version() or "unknown"
