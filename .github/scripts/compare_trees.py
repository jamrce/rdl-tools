"""Compare the per-OS trees `generate_fixture_tree.py` produced, byte for byte.

Raw bytes, with no line-ending normalisation: a module commits these files, so a CRLF that
differs by platform is a diff in every module repository.

    python .github/scripts/compare_trees.py trees
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(root: Path) -> int:
    trees = sorted(p for p in root.iterdir() if p.is_dir())
    if len(trees) < 2:
        print(f"need at least two trees to compare, found {len(trees)} in {root}", file=sys.stderr)
        return 1
    print("comparing:", ", ".join(t.name for t in trees))

    base, *rest = trees
    failures: list[str] = []
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        relative = path.relative_to(base)
        expected = path.read_bytes()
        for other in rest:
            twin = other / relative
            if not twin.exists():
                failures.append(f"{relative}: missing from {other.name}")
                continue
            found = twin.read_bytes()
            if found == expected:
                continue
            same_text = found.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n")
            detail = "line endings only" if same_text else "content"
            failures.append(f"{relative}: {base.name} and {other.name} differ ({detail})")

    for other in rest:
        extra = {p.relative_to(other) for p in other.rglob("*") if p.is_file()}
        extra -= {p.relative_to(base) for p in base.rglob("*") if p.is_file()}
        failures += [f"{relative}: only in {other.name}" for relative in sorted(extra)]

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"identical across every runner ({sum(1 for p in base.rglob('*') if p.is_file())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
