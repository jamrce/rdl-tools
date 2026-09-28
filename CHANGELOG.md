# Changelog

Notable changes to `rdl-tools`. The format follows [Keep a Changelog](https://keepachangelog.com/), and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

- `rdl-tools render-site-data` writes only `--rdl-accent-{100..900}` to `accent.generated.css`: no aliases, no `--ifm-color-primary-*`, no dark block. Module forked from older template whose `custom.css` lacks aliases or dark `color-mix` tint: copy them from current template. ([#8](https://github.com/jamrce/rdl-tools/issues/8))
- `rdl-tools render-site-data` emits `<Abstract />` in `reference.mdx`, between `<ReferenceHeader />` and `<Intro />`. Before bumping rdl-tools, add `Abstract` export to `@site/src/components/rdl` from rdl-module-template, else site build fails. Re-run `render-site-data`, else `--check` fails. ([#10](https://github.com/jamrce/rdl-tools/issues/10))
- `rdl-tools render-site-data` warns on stderr when `website/static/v{version}/ont/` is missing and `DOWNLOAD_FORMATS` is non-empty: run `render-docs` first. Still writes, exits 0. `DOWNLOAD_FORMATS=` silences it. ([#11](https://github.com/jamrce/rdl-tools/issues/11))
- `rdl-tools render-site-data` strips source indentation and edge blank lines from every literal; line breaks kept. `title`, `tagline`, `ontology.title` and `rdfs:label` headings collapse to one line. Re-run `render-site-data` to update generated JSON. ([#9](https://github.com/jamrce/rdl-tools/issues/9))
- End-to-end suite now asserts on generated `{version}.json` IRIs and `releases.json` contents after full run. No behaviour change. ([#15](https://github.com/jamrce/rdl-tools/issues/15))
- `rdl-tools render-site-data --draft-changelog` no longer lists existing shapes as `Added a SHACL constraint on …` when previous pin holds no shapes, as every `render-docs` pin does. Delete false bullets from existing unpublished `changelog/v*.md` drafts. ([#21](https://github.com/jamrce/rdl-tools/issues/21))
- `rdl-tools init`: `spec/` file identical to what it was generated from is skipped, so `--force` reruns work. Duplicate-version error prints paths. Plan lists shapes rename, `github/` rename, `.gitkeep` deletions; none runs before `Proceed?`. `Rename?` prompt gone. ([#22](https://github.com/jamrce/rdl-tools/issues/22))
- `rdl-tools render-docs` stamps `owl:versionIRI`/`owl:priorVersion` as `https://w3id.org/{W3ID_AUTHORITY}/{MODULE_SLUG}/v{version}/ont`, not ontology IRI. It and `render-site-data` exit 2 unless `.env` sets both keys. Derived module with published pins: `owl:priorVersion` chain becomes mixed. ([#24](https://github.com/jamrce/rdl-tools/issues/24))

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
