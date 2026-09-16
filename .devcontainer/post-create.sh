#!/bin/sh
# Shared setup, run once per container create. Committed — this is what every contributor gets.
#
# Personal, uncommitted extras go in .devcontainer/*.local.sh instead of here — see
# post-create.local.sh.example. Each is gitignored individually, so several contributors can keep
# their own without colliding.
set -eu

# Docker creates both mount points as root, so they are chowned before uv writes to them.
sudo chown -R vscode:vscode /workspace/.venv /home/vscode/.cache/uv
uv venv --python 3.13
uv pip install -e '.[dev]'
uv tool install pre-commit
pre-commit install

for hook in /workspace/.devcontainer/*.local.sh; do
    [ -e "$hook" ] || continue # the glob itself when nothing matches it
    echo "post-create.sh: running $hook"
    sh "$hook"
done
