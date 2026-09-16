"""One module per subcommand, each exposing `add_parser(parser)` and `run(args) -> int`.

`rdl_tools.cli.COMMANDS` is the registry; a module here is imported only when its command runs.
"""

from __future__ import annotations
