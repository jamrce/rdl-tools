"""Build CLI for RDL ontology modules. Every generator a module runs is a subcommand here."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib import import_module
from types import ModuleType
from typing import NamedTuple

from . import __version__


class Command(NamedTuple):
    module: str  # the module under rdl_tools.commands that implements it
    help: str


# The registry, and the order `rdl-tools --help` lists: setup, then the build, then maintainer-only.
# `help` lives here rather than in the module so that listing the commands imports none of them.
COMMANDS: dict[str, Command] = {
    "init": Command("init", "Configure a module checkout: derive its .env and spec/ from the RDF on disk"),
    "validate": Command("validate", "Parse spec/, refuse misplaced shapes, and run SHACL validation"),
    "format": Command("fmt", "Canonicalise the ontology Turtle in spec/ so diffs show semantics, not layout"),
    "expand-pins": Command("expand_pins", "Rebuild the derived serialisations and v0/ copy under website/static/"),
    "render-docs": Command("render_docs", "Write the immutable website/static/v{version}/ont/ artifact tree"),
    "render-site-data": Command("render_site_data", "Generate the JSON, MDX and CSS the Docusaurus site renders"),
    "fetch-fonts": Command(
        "fetch_fonts", "Re-download the self-hosted Barlow woff2 set (maintainer-only; needs network)"
    ),
}


def load(name: str) -> ModuleType:
    """Import one subcommand's module. Each supplies `add_parser(parser)` and `run(args) -> int`."""
    return import_module(f".commands.{COMMANDS[name].module}", __package__)


def selected_command(argv: Sequence[str]) -> str | None:
    """The first bare word in argv. No global option takes a value, so it is the subcommand."""
    return next((arg for arg in argv if not arg.startswith("-")), None)


def build_parser(command: str | None = None) -> argparse.ArgumentParser:
    """The parser, with full arguments for `command` only. Every other subcommand is a name and a
    help line, which is what keeps `--help` from importing rdflib seven times."""
    parser = argparse.ArgumentParser(
        prog="rdl-tools",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"rdl-tools {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    for name, spec in COMMANDS.items():
        if name != command:
            subparsers.add_parser(name, help=spec.help, add_help=False)
            continue
        module = load(name)
        subparser = subparsers.add_parser(
            name,
            help=spec.help,
            description=module.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        module.add_parser(subparser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = build_parser(selected_command(arguments)).parse_args(arguments)
    return int(load(args.command).run(args))


if __name__ == "__main__":
    raise SystemExit(main())
