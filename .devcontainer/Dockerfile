FROM debian:bookworm-slim

# curl and ca-certificates fetch uv; git is needed by the tooling. Nothing else is required:
# no subcommand of rdl-tools needs Node, and the suite fakes every npm call.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git sudo \
    && rm -rf /var/lib/apt/lists/*

# uv supplies both interpreters as standalone builds, so Debian's python3 never matters.
# UV_PYTHON_INSTALL_DIR is a stable image path: a .venv on the bind mount keeps resolving after
# a rebuild, which a path under $HOME does not.
ARG UV_VERSION=0.12.15
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_INSTALL_DIR=/usr/local/bin sh
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
ARG PYTHON_VERSIONS="3.13 3.14"
RUN uv python install ${PYTHON_VERSIONS} && chmod -R a+rX /opt/uv-python

# The cache is a host bind mount and the venv is a named volume — different filesystems, so uv
# cannot hardlink between them.
ENV UV_LINK_MODE=copy

# Personal tooling (a preferred indexer, a linter nobody else on the team runs) does not belong
# baked into an image every contributor pulls. See .devcontainer/post-create.local.sh.example.

# safe.directory: a WSL2 bind mount can carry a uid git will not accept as the tree's owner.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && mkdir -p /home/$USERNAME/.claude && chown -R $USER_UID:$USER_GID /home/$USERNAME/.claude \
    && git config --system --add safe.directory /workspace

# Where `uv tool install` puts its entry points.
ENV PATH=/home/$USERNAME/.local/bin:$PATH

USER $USERNAME
WORKDIR /workspace
