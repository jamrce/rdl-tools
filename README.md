# rdl-tools

Build CLI for Reference Data Library (RDL) ontology modules.

An RDL module is a Git repository holding one RDF(S)/OWL ontology, its SHACL shapes, and a Docusaurus documentation site published to GitHub Pages under a permanent `w3id.org` identifier. `rdl-tools` is a single installable package that turns the ontology into a publishable site: it validates the RDF, canonicalises the Turtle, writes an immutable artifact tree per version, and generates everything the site renders.

Modules therefore carry no build code — not one `.py` file. Fixing a generator is one release here plus a version bump per module, rather than the same edit repeated in every module repository.

`rdl-tools` is not a general-purpose RDF toolkit. It reads and writes the layout defined by [rdl-module-template](https://github.com/jamrce/rdl-module-template) — `spec/`, `.env`, `changelog/`, `website/src/generated/` — and refuses a folder that is not a checkout of it. Every module starts as a copy of that template; see [ADR-001](docs/adrs/ADR-001-no-module-skeleton-in-the-package.md).

## Requirements

Python 3.13 or later, tested on 3.13 and 3.14. Two runtime dependencies install with it, pinned to exact versions: `rdflib==7.6.0` and `pyshacl==0.40.1`. Nothing else, and no subcommand needs Node.

The development toolchain — `uv`, `pytest`, `coverage`, `ruff`, `mypy`, `twine` — is the `dev` extra. [CONTRIBUTING.md](CONTRIBUTING.md) covers setup.

## Getting started

Create your module from the template on GitHub ("Use this template"), clone it, then:

```sh
pip install rdl-tools
rdl-tools init
```

`init` reads whatever RDF is already in the checkout, derives every configuration value it can, prompts for what RDF cannot supply, and finishes local setup. Drop your ontology in at the folder root or in `spec/` before running it; a file that asserts `sh:NodeShape` is recognised as shapes by content, not by its name, and renamed to `*.shacl.ttl`. A discovered `.ttl` that asserts neither `sh:NodeShape` nor `owl:Ontology` is refused by name, never adopted. Given several versions — `--from <dir>`, or pins already under `website/static/` — `spec/{module}.ttl` is written from the highest version alone, and each version keeps its own pin: an immutable release snapshot, unrelated to *pinning* a dependency version above. See [ADR-002](docs/adrs/ADR-002-only-committed-turtle-per-pin.md).

`spec/` holds ontology and shapes only: `{module}.ttl`, `{module}.shacl.ttl`, and the `{module}.generated.ttl` provenance ledger, which `rdl-tools` copies into each pin but never writes itself. Any other compound-suffix Turtle there — an export, instance data, notes — is refused by name rather than merged into the published graph. See [ADR-004](docs/adrs/ADR-004-two-allow-lists-for-turtle.md).

In a module's CI, install from the pinned lockfile and call the CLI directly:

```yaml
- run: pip install -r requirements.txt   # rdl-tools==X.Y.Z, pinned exactly
- run: rdl-tools validate --spec-dir spec
```

Pin an exact version, never a range: a module's build must not change because a new tool shipped.

## Commands

| Command | What it does |
| --- | --- |
| `init` | Configure a module checkout: derive its `.env` and `spec/` from the RDF on disk |
| `validate` | Parse `spec/`, refuse misplaced shapes, and run SHACL validation |
| `format` | Canonicalise the ontology Turtle in `spec/` so diffs show semantics, not layout |
| `expand-pins` | Rebuild the derived serialisations and `v0/` copy under `website/static/` |
| `render-docs` | Write the immutable `website/static/v{version}/ont/` artifact tree |
| `render-site-data` | Generate the JSON, MDX and CSS the Docusaurus site renders |
| `fetch-fonts` | Re-download the self-hosted Barlow `woff2` set (maintainer-only; needs network) |

Every command takes `--help`. `python -m rdl_tools` works wherever the console script is not on `PATH`. Exit codes are `0` for success, `1` when the thing under test failed, `2` when the inputs were wrong.

`validate` resolves `owl:imports` by default, dereferencing each imported IRI over the network so shapes targeting an upstream class see its hierarchy. `--no-imports` skips it — use it offline or in a sandboxed CI job.

## Ordering constraints

The commands are not independent. What order to run them in for a new module or a release is defined by [rdl-module-template](https://github.com/jamrce/rdl-module-template) — its `validate.yml` and `release.yml`, and `docs/getting-started-manually.md` for the tool-free equivalent. Three constraints those sequences exist to satisfy:

- **`render-docs` before `render-site-data`.** The version list is built by scanning the pins under `website/static/`, and a historical release with no changelog entry gets its date from the pin's own `ont.ttl`.
- **A Docusaurus doc version is cut before the next release renders.** `reference.mdx` is one working copy, overwritten in place; render past an uncut version and that page is gone. [ADR-003](docs/adrs/ADR-003-doc-version-snapshot-per-release.md)
- **`expand-pins` after the commit, before any build.** What it writes is git-ignored, so committing first keeps derived files out of the tree; skipping it 404s every historical download link, `npm start` in a fresh checkout included. [ADR-002](docs/adrs/ADR-002-only-committed-turtle-per-pin.md)

## What the generators guarantee

Same `spec/` and `.env`, byte-identical committed output. Asserted end to end, from the built wheel, in `tests/test_e2e.py`.

Published bytes are immutable: `format` refuses to rewrite anything under `website/static/`, and `render-docs` refuses to overwrite an existing pin without `--force`, because a `w3id.org` URL has already served those bytes.

## Contributing

Setup, the pre-PR checks and the release process are in [CONTRIBUTING.md](CONTRIBUTING.md). Security boundaries and how to report a vulnerability are in [SECURITY.md](SECURITY.md).

## Licence

MIT — see [LICENSE.md](LICENSE.md).
