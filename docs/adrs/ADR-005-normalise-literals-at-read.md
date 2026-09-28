# ADR-005 — Literals are cleaned once at read, and collapsed only where a line break cannot go

- **Status:** Accepted, implemented
- **Date:** 2026-09-28

## Context

A Turtle `"""…"""` literal keeps the newlines, indentation and edge blank lines of the file it was written in. `render-site-data` copied every literal verbatim into `site.json` and `{version}.json`, so a wrapped `dcterms:description` reached the `<meta name="description">` tag, and a wrapped `rdfs:label` broke its `###` heading in `reference.mdx`.

Issue #9 proposed two normalisations chosen per field: one collapsing to a single line, and one joining wrapped lines while keeping blank-line paragraph breaks, with `skos:example` exempt. The paragraph rule destroys any structure inside a literal. So every field that may hold a Turtle snippet needs its own exemption, not only `skos:example` but also a `skos:scopeNote` or `skos:definition` that quotes one. And every new field needs a decision.

rdflib parses `"""a\n b"""` and `"a\n b"` to the same `Literal`, so the quote style cannot select the treatment.

The site template in `rdl-module-template` renders every prose field as plain JSX text under `white-space: normal`, so a single newline already renders as a space.

## Decision

Two layers, neither chosen per field.

`pick_literal` and `pick_literals` pass every literal through `clean_literal`: CRLF becomes LF, then `inspect.cleandoc` strips leading and trailing blank lines and the indentation common to the second and later lines. Line breaks, blank-line paragraph breaks and relative indentation survive, so the same rule serves prose and examples.

`single_line` collapses every whitespace run to one space, and is applied only where the destination cannot hold a line break: the module title (`site.title`, `ontology.title`, the page front matter), `site.tagline`, the `description` front matter, and a term label taken from `rdfs:label`.

## Consequences

- A new field read through `pick_literal` or `pick_literals` is cleaned without a decision. Only a new single-line destination needs one.
- A tab in a literal expands to 8 spaces. A first line with content loses its own leading indentation, as a docstring's does.
- When a literal's text starts on the same line as its opening quotes, the indentation of the later lines cannot be told apart from the source's: rdflib does not report the literal's column. The margin is then taken from the later lines alone, so an indented example written this way loses its relative indentation. An example keeps its shape when its text starts on the line after `"""`.
- Every literal is trimmed at its ends, including `owl:versionInfo`, namespaces, dates, `dcterms:publisher` and `sh:message`.
- Prose fields keep their single `\n` and `\n\n` in the JSON. Rendering paragraphs as separate `<p>` elements, and examples in `<pre>`, are template changes.
- Literals differing only in source indentation become one entry in a `pick_literals` list.
- `diff_bullets` still compares raw literals, so re-indenting a definition still drafts a "Reworded" bullet.
