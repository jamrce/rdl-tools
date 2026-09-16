# Contributing

## Reporting and proposing

Bugs and feature requests go in [Issues](https://github.com/jamrce/rdl-tools/issues). Include the `.ttl` that triggered a generator bug, reduced if you can. Vulnerabilities go through private reporting instead — see [SECURITY.md](SECURITY.md).

Open an issue before any pull request. Every module pins an exact version of this package and regenerates its published site from it, so a change in output is a change in every module repository.

Contributions are accepted under the MIT licence in [LICENSE.md](LICENSE.md), and everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setup

[uv](https://docs.astral.sh/uv/) is required. It is the build frontend, the publisher, and the source of both test interpreters; `tests/conftest.py` skips the packaging tests without it.

```sh
uv python install 3.13 3.14
uv venv --python 3.13 && uv pip install -e ".[dev]"
```

`.devcontainer/` does all of the above on create, and wires the git hook too: uv and both interpreters are baked into the image, and the container then builds the venv, installs the `dev` extra, and runs `pre-commit install`.

Outside the devcontainer, that hook is opt-in — `pre-commit` runs the formatting half of CI before each commit:

```sh
uv tool install pre-commit && pre-commit install
```

CI runs the suite on 3.13 and 3.14. For the second leg locally, uv supplies a standalone interpreter, so the system Python does not matter:

```sh
uv venv --python 3.14 .venv-314 && uv pip install --python .venv-314/bin/python -e ".[dev]"
.venv-314/bin/python -m pytest
```

There is one suite, and it includes the end-to-end tests: they build the wheel, install it into a fresh environment with uv, and drive every generator through the installed console script. That is what proves the packaging. uv's cache makes it fast and offline after the first run; without uv on `PATH` those tests skip and say so.

`pytest -m network` is the one opt-in set. It hits the Google Fonts API and nothing in CI runs it.

## Making a change

### Style

Inline `#` comments: one line wherever one will do, two at the most. Longer rationale goes in an ADR under [docs/adrs/](docs/adrs/), referenced from the code. Each fact is stated in one place — README for users, this file for contributors, ADRs for decisions.

### Invariants a PR must not break

- **One implementation of every generator.** Build logic lives here and only here. A module repo carries no `.py` files at all.
- **One skeleton, in rdl-module-template.** This package ships no copy of it. `tests/test_packaging.py` fails if one, or a lockfile, or a web font, appears in the wheel. [ADR-001](docs/adrs/ADR-001-no-module-skeleton-in-the-package.md)
- **Deterministic generators.** The same input produces byte-identical committed output.
- **Published artefacts are immutable.** Nothing may rewrite bytes under `website/static/` that a `w3id.org` URL has already served. [ADR-002](docs/adrs/ADR-002-only-committed-turtle-per-pin.md)
- **A generator fix ships as a release plus a version bump per module**, never as an edit in a module repository.

### Adding a subcommand

1. Add a module under `src/rdl_tools/commands/` exposing `add_parser(parser)`, which adds arguments to the subparser it is given, and `run(args) -> int`. Its module docstring becomes the subcommand's `--help` description.
2. Register it in `rdl_tools.cli.COMMANDS` with its module name and one-line help, and list it in `tests/test_cli.py::EXPECTED_COMMANDS` and the README table.
3. Add its tests, and its determinism assertion to `tests/test_e2e.py` if it writes anything a release commits.

`COMMANDS` holds the help text rather than the module so that `rdl-tools --help` can list every command without importing any of them — a command module is imported only when its command runs, which keeps `--help` and `--version` off rdflib's ~350 ms import. `tests/test_cli.py` asserts that.

Exit codes follow the existing convention: `0` success, `1` the thing under test failed, `2` the inputs were wrong — a missing directory, a malformed spec.

## Before opening a PR

Everything `ci.yml` runs, in the same order:

```sh
uv lock --check
ruff check src tests
ruff format --check src tests
python -m compileall -q src tests
mypy
coverage run -m pytest && coverage report      # fails under 90%
uv build && twine check dist/*
```

Pass `dist/*` rather than `dist/`: `uv build` writes a `.gitignore` beside the artefacts, shell globs skip dotfiles, and `twine` rejects anything it cannot parse as a distribution.

`uv lock --check`: fails on any `dependencies`/`optional-dependencies`/`version` edit not followed by `uv lock`. Not release-only.

## Maintainers

### Running the workflows locally

[`nektos/act`](https://github.com/nektos/act) needs Docker. It covers the `lint`, `test` and `standalone-checkout` jobs and the build half of `package`. It cannot cover OIDC, so nothing in `publish.yml` past the version check, nor artifact upload and download without `--artifact-server-path`, nor GitHub Pages.

```sh
act -W .github/workflows/ci.yml -P ubuntu-latest=catthehacker/ubuntu:full-latest \
    --matrix python-version:3.13
```

Run one matrix leg at a time. act's legs share a tool cache, and concurrent `setup-python` runs against it produce import failures no real runner reproduces.

### Releasing

1. Move `CHANGELOG.md`'s `Unreleased` section under the new version, dated.
2. Set the version in both places that carry it: `version` in `pyproject.toml` and `__version__` in `src/rdl_tools/__init__.py`. A test asserts the pair agrees, and `publish.yml` asserts the tag against both.
3. `uv lock`, and commit the result if it moved.
4. Tag `vX.Y.Z` and push the tag.

`publish.yml` then runs `uv build` and `uv publish`. A version ending in `aN`, `bN` or `rcN` goes to TestPyPI; anything else goes to PyPI. Both use Trusted Publishing, so no API token exists in this repository.

### Bumping the Python range or a pinned dependency

Neither is one edit. Each place below states the fact for its own reason, so nothing here restates them — this is only the checklist of where they live, in one place.

- **A new or dropped supported Python version**: `requires-python` and the `Programming Language :: Python :: 3.1x` classifier in `pyproject.toml`; the `test`/`package` matrices in `ci.yml`; `PYTHON_VERSIONS` in `.devcontainer/Dockerfile`; the `uv python install` / `.venv-314` commands above; `[tool.mypy].python_version` if the floor itself moves.
- **`rdflib` or `pyshacl`**: the pin in `pyproject.toml`'s `dependencies`, then `uv lock`. Exact versions only — see README's "Requirements" section for why.

Grep for the current version number before changing it; a place missed here is a place this list is out of date, not a place exempt from updating.
