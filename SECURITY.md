# Security policy

## Supported versions

Only the latest released version of `rdl-tools` receives fixes.

## Reporting a vulnerability

Report privately through GitHub's [private vulnerability reporting](https://github.com/jamrce/rdl-tools/security/advisories/new) rather than opening a public issue. Expect an acknowledgement within seven days.

## What this package does

`rdl-tools` reads RDF and configuration from the working directory and writes generated files back into it. Its boundaries:

- **Network access.** Only `rdl-tools fetch-fonts` makes a network request of its own, and only to an allow-list of hosts (`fonts.googleapis.com`, `fonts.gstatic.com`, `raw.githubusercontent.com`), each with a timeout. `rdl-tools validate` resolves `owl:imports` by default, so an ontology under test can cause an outbound request, exactly as under any RDF tool; `--no-imports` turns that off.
- **Subprocesses.** Only `rdl-tools init` runs one, and only during local setup: `python -m venv`, `pip install -r requirements.txt` and `npm install`, all inside the target folder. `--skip-install` disables that step entirely and is what CI uses.
- **Writes.** Every command writes only inside the module directory it was given. `init` records what it generated in `.rdl-tools-manifest.json`, and `--clean` removes exactly that set — never a hand-written file.
- **Untrusted input.** Treat a `.ttl` file, a `.env` file and a `changelog/*.md` file as untrusted input to these commands: they are parsed, and their content reaches generated pages.

## Supply chain

- Dependencies (`rdflib`, `pyshacl`) are pinned to exact versions.
- Releases publish through PyPI Trusted Publishing; no API token exists in this repository.
- Third-party GitHub Actions are pinned to full commit SHAs.
