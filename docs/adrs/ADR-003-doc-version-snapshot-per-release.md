# ADR-003 — A Docusaurus doc version snapshot is cut for every release

- **Status:** Accepted, implemented
- **Date:** 2026-09-06

## Context

`website/docs/reference.mdx` is the generated reference page documenting the ontology's terms — classes, properties, shapes. `render-site-data` writes it as a single working copy, overwritten in place on every run. It is not one file per version.

The only durable record of a past version's reference page is a Docusaurus doc version snapshot: `website/versioned_docs/version-{v}/`, registered in `website/versions.json`. Rendering a new version without having snapshotted the previous one does not fail — it silently overwrites the old page, and the old content is gone.

## Decision

A snapshot is cut for whatever was latest before the next version is rendered. `release.yml` in the module template does this automatically, in order: `render-docs`, `render-site-data`, `npx docusaurus docs:version`, commit.

A manual or local run must do the same. `render-site-data` does not cut the snapshot itself: `docs:version` is a Docusaurus CLI command that needs `node_modules`, and no subcommand of `rdl-tools` requires Node.

## Consequences

- Cutting a version out of the tagged release path is a manual two-step, and getting the order wrong loses a page rather than raising an error.
- `init` can backfill a module's history from Turtle files that already represent past releases, stamping each as a pin. Those historical pins get no snapshot and no `reference.mdx`: they are RDF-only by design. The artifact tree resolves for them; the documentation page does not exist for versions that predate the module's website.
