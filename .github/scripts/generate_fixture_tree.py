"""Generate a module's committed artefacts from the test fixture, into a given directory.

Run on each OS in CI so `compare_trees.py` can diff the results byte for byte. Only what a
release actually commits is collected: the derived serialisations reorder on every run by
design, so they prove nothing about the platform. See docs/adrs/ADR-002.

    python .github/scripts/generate_fixture_tree.py out
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "sample-ont"
VERSION = "0.5.7"

COMMITTED = (
    f"website/static/v{VERSION}/ont/ont.ttl",
    "website/src/generated/site.json",
    "website/src/generated/releases.json",
    f"website/src/generated/{VERSION}.json",
    "website/src/generated/index.js",
    "website/docs/reference.mdx",
    f"changelog/v{VERSION}.md",
)


def main(out_dir: Path) -> int:
    # Off to one side: out_dir's parent is the checkout, and a stray module there would be
    # picked up as a tree of its own.
    work = Path(tempfile.mkdtemp()) / "module"
    shutil.copytree(FIXTURE, work)

    for argv in (
        ["render-docs", "--module-dir", str(work), "--version", VERSION],
        ["render-site-data", "--module-dir", str(work), "--version", VERSION, "--draft-changelog"],
    ):
        result = subprocess.run([sys.executable, "-m", "rdl_tools", *argv], check=False)
        if result.returncode != 0:
            return result.returncode

    shutil.rmtree(out_dir, ignore_errors=True)
    for relative in COMMITTED:
        source = work / relative
        if not source.exists():
            print(f"{relative} was not generated", file=sys.stderr)
            return 1
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        print(f"collected {relative} ({source.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
