# ADR-001 — The package ships no module skeleton

- **Status:** Accepted, implemented
- **Date:** 2026-09-06

## Context

A *module* here is a self-contained ontology package: authored Turtle, a generated documentation website, and CI workflows, published as its own repository. A *skeleton* is the file set a new module starts from — the website scaffold, workflow files, config defaults — copied once and then owned and edited by that module.

A skeleton and a build tool are different things with different lifecycles: a skeleton is a static starting point copied once, a build tool is logic that runs repeatedly against whatever is on disk. Packaging both together would force every website file, workflow and config default to exist in two places and stay identical between them, with a drift check standing in for the fact that they should be decoupled.

## Decision

The skeleton lives in `rdl-module-template` — a separate repository where a new module is created by copying, not by installing this tool. `rdl-tools` is a helper that runs *inside* a module checkout: it reads what is on disk, derives configuration, writes generated files, and refuses a folder missing either `website/` or `requirements.txt`.

A module therefore starts by copying the template repository, never by running a command.

## Consequences

- No drift check, because there is nothing to keep in sync.
- The wheel stays small: no skeleton, lockfile or web font ships in it, and `tests/test_packaging.py` fails if any of them reappear.
- `init` cannot help someone with a bare folder of Turtle. It exits `2` and names the template.
- The tool is bound to the template's layout: `spec/`, `website/src/generated/`, `website/docs/reference.mdx`, `github/workflows/`. It is a build tool for repositories shaped like that template, not a general-purpose RDF toolkit.
