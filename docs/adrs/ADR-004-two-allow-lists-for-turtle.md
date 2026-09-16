# ADR-004 — `spec/` allows Turtle by filename, the import paths by content

- **Status:** Accepted, implemented
- **Date:** 2026-09-08

## Context

`spec/` is the folder holding a module's authored Turtle — its ontology source and SHACL shapes. Everything in it is merged into the published graph and serialised into a pin (see ADR-002), and a published pin cannot be corrected: `render-docs` refuses to overwrite one, and a `--force` rewrite of published bytes breaks the append-only guarantee. So what `spec/` admits has to be decided by rule, not by exclusion. A companion Turtle file carrying instance data declares no `owl:Ontology` and asserts no `sh:NodeShape`, so neither the single-ontology gate nor the shapes-in-ontology gate sees it — a deny-list of known-bad suffixes would let it through.

There are two other places `rdl-tools` reads Turtle from besides `spec/`: `init` discovering existing files when bootstrapping a module, and `--from` when backfilling a module's history from a dump. Both take arbitrary files, where filenames are unreliable: a dumped `mymodule.0.1.0.ttl` trails as `0.ttl`.

## Decision

Two allow-lists, one per problem.

`spec/` is curated and authored, so the rule is on the filename: `<stem>.ttl` is an ontology source; two or more dots means the trailing `<suffix>.ttl` must be in `SUPPORTED_COMPOUND_SUFFIXES` — `shacl.ttl` and `generated.ttl`, each with a handler. Anything else is refused by name, exit 2. `rdl-tools` names no suffix it does not implement.

The import paths classify by content: `sh:NodeShape` → shapes, `owl:Ontology` → ontology, neither → refused by name, exit 2. The filename rule is deliberately *not* applied there, and version resolution handles the dumped form — `owl:versionInfo`, then the `owl:versionIRI` segment, then `X.Y.Z` in the filename stem, then `dcterms:modified`/`created`, refusing to guess when none resolves. A file destined to become the ontology must carry an `owl:Ontology` subject or fail `require_single_ontology` regardless.

`init` writes the *live spec* — the current, editable contents of `spec/`, as opposed to the immutable historical pins — from one version's own graph, the highest, rather than from the union of the candidates it merged. A union of several versions resurrects retired terms and makes `owl:versionInfo`, `dcterms:modified` and `dcterms:title` multi-valued on a single subject. The union still serves the namespace-conflict and single-`owl:Ontology` checks, where it is exactly the right graph, and each version's pin is stamped from its own graph.

## Consequences

- A module author keeps exports, notes and instance data outside `spec/`. The refusal names the file and the supported names.
- Adding a compound suffix later is one entry in `SUPPORTED_COMPOUND_SUFFIXES` plus its handler.
- Neither refusal is ever a silent skip: a file that disappears from the build without a word is worse than a build that stops.
- Two ontology candidates resolving to the same version are refused by name — one of them would decide the live spec and both would claim one pin directory.
- Shapes are unioned across imported versions, unlike the ontology. Shapes carry no version of their own and a pin holds none, and a retired shape targeting a removed class never matches, so the union is inert rather than wrong. Preserving shapes per version belongs to the historical-version backfill.
