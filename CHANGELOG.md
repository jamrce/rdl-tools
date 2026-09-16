# Changelog

Notable changes to `rdl-tools`. The format follows [Keep a Changelog](https://keepachangelog.com/), and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-16

- `rdl-tools init` — configure a module checkout taken from `rdl-module-template`: derive every `.env` value it can from the `.ttl` on disk, prompt only for what RDF cannot supply, activate CI and finish local setup. Refuses a folder that is not a module checkout.
- Import classification by content: `sh:NodeShape` makes a file shapes and it is renamed `*.shacl.ttl`, `owl:Ontology` makes it an ontology source, and a file asserting neither is named on stderr and refused with exit 2.
- Multi-version import through `init --from <dir>` and pins already under `website/static/`: one immutable pin per version, with a chained `owl:priorVersion` and a drafted changelog. `spec/{module}.ttl` is written from the highest version's own graph. Two files resolving to one version are refused by name.
- A `spec/` filename rule enforced by every command that reads it: `{module}.ttl` is ontology source, `{module}.shacl.ttl` is shapes, `{module}.generated.ttl` is the provenance ledger, and any other compound-suffix Turtle is refused with exit 2.
- `rdl-tools validate` — parse `spec/`, refuse shapes declared outside a `*.shacl.ttl` file, and run SHACL validation.
- `rdl-tools format` — canonicalise the ontology Turtle in `spec/`. Shapes and the generated ledger are left alone unless named with `--ontology`. `--check` reports without writing.
- `rdl-tools render-docs` — write the immutable `website/static/v{version}/ont/` artifact tree in four serialisations.
- `rdl-tools render-site-data` — generate the JSON, MDX and CSS the Docusaurus site renders.
- `rdl-tools expand-pins` — rebuild the derived serialisations and the `v0/` copy from committed Turtle.
- `rdl-tools fetch-fonts` — re-download the self-hosted Barlow set. Maintainer-only, and the only subcommand that opens a socket.
- `--version` on the CLI, and `python -m rdl_tools` wherever the console script is not on `PATH`.
- Inline type information (`py.typed`), checked under `mypy --strict`. Requires Python 3.13 or later; tested on 3.13 and 3.14.
