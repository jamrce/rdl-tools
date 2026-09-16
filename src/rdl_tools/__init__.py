"""Build CLI for RDL ontology modules."""

from __future__ import annotations

__all__ = ["__version__"]

# Kept in step with pyproject.toml's `version` by tests/test_packaging.py, and asserted against
# the release tag by publish.yml.
__version__ = "0.1.0rc4"
