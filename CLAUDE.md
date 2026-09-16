# rdl-tools — agent notes

Python CLI published to PyPI. A module consumes it as `pip install rdl-tools==X.Y.Z`, then `rdl-tools <subcommand>`. This repository is standalone: nothing in it may reference a path outside its own folder, and `ci.yml`'s `standalone-checkout` job fails if anything does.

## Layout

- `cli.py` dispatches via the `COMMANDS` registry — see its docstring for why help lives there instead of in each module.
- `commands/` — one module per subcommand (`add_parser(parser)`, `run(args) -> int`). Note: `fmt.py` publishes as `format`, the one name mismatch.
- Root-level modules (`spec.py`, `colour.py`, etc.) are shared library code, no argparse.
- `docs/adrs/` — decisions the code points at rather than restating.

## Working here

```sh
uv venv --python 3.13 && uv pip install -e ".[dev]"
.venv/bin/python -m pytest              # one end-to-end suite
```

`mypy --strict`, `ruff check` and `ruff format --check` are hard gates. The coverage floor is 90%. [CONTRIBUTING.md](CONTRIBUTING.md) has the full pre-PR list, invariants and release steps — this section only adds what CONTRIBUTING doesn't already say.

## Rules a change must not break

- **Every generator lives here.** Adding one means adding a `commands/` module and listing it in `COMMANDS` — never a script elsewhere. (Same invariant as CONTRIBUTING.md; restated because it's the one most likely to be broken by habit.)
- `expand-pins` output specifically is excluded from the determinism assertion in `tests/test_e2e.py` — see ADR-002.
- **Version bump is two edits, not one**: `pyproject.toml` and `rdl_tools.__version__`, checked by a test and by `publish.yml` against the release tag.

## Sharp edges

- **Versions are only ever cut forward.** `spec.find_previous_pin` means "highest pin that is not this one", not "highest pin below this one", so rendering an older version after a newer one exists chains its `owl:priorVersion` to the newer pin. Nothing detects this; what prevents it is `render-docs` refusing to overwrite an existing pin, so reaching it takes a deliberate `--force`. Backfilling history is `init --from`'s job, which stamps each pin in ascending order.
- **`render-docs` and `expand-pins` delete `website/static/v0/` wholesale** before rewriting it, including any `index.html` Docusaurus built there. Run them before the site build, never after.

## Style

Inline `#` comments are one line, two at most. Longer rationale requires an ADR under `docs/adrs/`, referenced from the code. Docstrings must say what a thing does and what would be surprising about it — not why alternatives were rejected (that's an ADR).

No filler, anywhere: comments, docstrings, prose docs. No reader-address (`you`/`your`) outside a how-to step, no personifying a tool or CI, no framing sentence before a list. State the fact, stop.

State each fact in one place. README is for users, CONTRIBUTING for contributors, ADRs for decisions; none of the three restates another.
