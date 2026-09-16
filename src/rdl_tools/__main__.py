"""`python -m rdl_tools` — the same entry point as the `rdl-tools` console script."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
