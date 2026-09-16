# ADR-002 — Only each pin's Turtle is committed; the rest of the artifact tree is derived

- **Status:** Accepted, implemented
- **Date:** 2026-09-06

## Context

Each released ontology version is a *pin*: an immutable, permanently addressable snapshot, published once and never edited again.

A release writes `website/static/v{version}/ont/` in four serialisations — `ont.ttl`, `ont.rdf`, `ont.jsonld`, `ont.nt` — plus a copy of the newest pin at `website/static/v0/ont/`. Every one of those files is served from a permanent `w3id.org` URL, so all of them must be present in a built site.

rdflib reorders triples on every serialisation, so committing all four formats would produce a large, unreadable diff on each release even when the graph has not changed — most of the churn in the tree would be noise, not signal.

## Decision

Only `website/static/v{version}/ont/ont.ttl` is committed. The other three serialisations and the whole `v0/` tree are git-ignored and rebuilt from that Turtle by `rdl-tools expand-pins`.

`expand-pins` runs in a module's `validate.yml` and `release.yml` before `npm run build`, and must be run by hand in a fresh checkout before `npm start`. Without it, every historical download link 404s.

## Consequences

- The authoritative bytes of a published pin are byte-immutable in git and reviewable in a pull request. `format` refuses to rewrite anything under `website/static/`, and `render-docs` refuses to overwrite an existing pin without `--force`.
- Rebuilt files are graph-identical to what `render-docs` wrote at release time, but not byte-identical. That is acceptable for a download and is why they are not committed.
- `expand-pins` output is excluded by name from the determinism assertions in `tests/test_e2e.py`. Determinism is claimed for committed output only.
