"""Fail if any tracked text file carries a CR.

`.gitattributes` normalises on the way in, but git's smudge filter only ever adds CRs on
checkout — it never strips them. A blob committed before that rule existed, or with a
`-text` attribute, stays CRLF in every working tree forever. Only this notices.

    python .github/scripts/check_line_endings.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def text_paths(listing: str) -> list[Path]:
    """Paths from `git ls-files --eol -z`, minus the ones git treats as binary.

    Each record is "i/lf<TAB>w/lf<TAB>attr/text=auto eol=lf<TAB>path"; a binary reads "i/-text".
    """
    return [Path(record.split("\t")[-1]) for record in listing.split("\0") if record and "i/-text" not in record]


def main() -> int:
    listing = subprocess.run(["git", "ls-files", "--eol", "-z"], capture_output=True, text=True, check=True).stdout
    offenders = [p for p in text_paths(listing) if p.is_file() and b"\r" in p.read_bytes()]
    if not offenders:
        return 0
    print("CR found in tracked text files:", file=sys.stderr)
    print("\n".join(f"  {p}" for p in offenders), file=sys.stderr)
    print("fix: pre-commit run mixed-line-ending --all-files", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
