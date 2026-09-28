# Changelog

Notable changes to `rdl-tools`. The format follows [Keep a Changelog](https://keepachangelog.com/), and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-28

- `rdl-tools render-site-data` writes only `--rdl-accent-{100..900}` to `accent.generated.css`: no aliases, no `--ifm-color-primary-*` and no dark block. A module forked from an older template whose `custom.css` lacks the aliases or the dark `color-mix` tint must copy them from the current template. ([#8](https://github.com/jamrce/rdl-tools/issues/8))
- `rdl-tools render-site-data` emits `<Abstract />` in `reference.mdx`, between `<ReferenceHeader />` and `<Intro />`. Before bumping `rdl-tools`, copy the `Abstract` export into `@site/src/components/rdl` from `rdl-module-template`, or the site build fails. Then re-run `render-site-data`, or the reference page shows no abstract. ([#10](https://github.com/jamrce/rdl-tools/issues/10))
- `rdl-tools render-site-data` warns on stderr when `website/static/v{version}/ont/` is missing and `DOWNLOAD_FORMATS` is non-empty, since `render-docs` has to run first. It still writes its output and exits 0. `DOWNLOAD_FORMATS=` silences the warning. ([#11](https://github.com/jamrce/rdl-tools/issues/11))
- `rdl-tools render-site-data` strips source indentation and leading and trailing blank lines from every literal, keeping line breaks. `title`, `tagline`, `ontology.title` and `rdfs:label` headings collapse to one line. Re-run `render-site-data` to update the generated JSON. ([#9](https://github.com/jamrce/rdl-tools/issues/9))
- The end-to-end suite asserts on the IRIs in the generated `{version}.json` and on the contents of `releases.json` after a full run. No behaviour change. ([#15](https://github.com/jamrce/rdl-tools/issues/15))
- `rdl-tools render-site-data --draft-changelog` no longer lists existing shapes as `Added a SHACL constraint on …` when the previous pin holds no shapes, which is true of every pin `render-docs` writes. Delete any such false bullets from unpublished `changelog/v*.md` drafts. ([#21](https://github.com/jamrce/rdl-tools/issues/21))
- `rdl-tools init` skips a `spec/` file identical to the source it was generated from, so `--force` reruns work. The duplicate-version error names each file by its path. The plan lists the shapes rename, the `github/` rename and each `.gitkeep` deletion, and none of them runs before `Proceed?` is answered. The separate `Rename?` prompt is gone. ([#22](https://github.com/jamrce/rdl-tools/issues/22))
- `rdl-tools render-docs` stamps `owl:versionIRI` and `owl:priorVersion` as `https://w3id.org/{W3ID_AUTHORITY}/{MODULE_SLUG}/v{version}/ont` rather than deriving them from the ontology IRI. It and `render-site-data` exit 2 unless `.env` sets both keys. A derived module that has already published pins gets a mixed `owl:priorVersion` chain. ([#24](https://github.com/jamrce/rdl-tools/issues/24))
- A Turtle syntax error, a non-UTF-8 `.ttl` file or an invalid `ACCENT_COLOR` is reported on one line with exit 2, instead of a traceback. Paths in messages are relative to the module folder. Run outside a module root, `render-docs`, `render-site-data`, `expand-pins` (previously exit 0) and `fetch-fonts` exit 2 and say to pass `--module-dir`. ([#26](https://github.com/jamrce/rdl-tools/issues/26))

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
