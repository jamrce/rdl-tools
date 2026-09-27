#!/bin/sh
# Claude Code PreToolUse hook for Bash. Exits 2, which blocks the call, when a git or gh write
# appears anywhere in the command: `git -C . commit`, `sh -c "git push"`, `a && git reset`.
#
# It greps the raw JSON payload rather than parsing it, so it needs nothing beyond POSIX tools.
# A mention of a write inside quoted text, such as `echo "git push"`, is blocked too.
set -u

# JSON escapes, quotes, substitutions and separators become spaces, so a nested command reads as a plain one.
flat=$(tr '\n' ' ' | sed -e 's/\\[nrt]/ /g' -e "s/[\"'\`\$();|&<>{}\\\\]/ /g")

S='(^|[^[:alnum:]_.-])'
E='([^[:alnum:]_-]|$)'
W='[[:space:]]+'
A='[^[:space:]]+'
# Global options before the subcommand: `-C <path>`, `-c <key=value>`, `--git-dir <path>`, flags.
GIT_OPTS="($W(-[Cc]$W$A|--(git-dir|work-tree|namespace|exec-path)$W$A|-$A))*"
GH_OPTS="($W(-R$W$A|--repo$W$A|-$A))*"

GIT_WRITES='add|am|apply|branch|checkout|cherry-pick|clean|commit|config|fetch|merge|mv|pull|push|rebase|reset|restore|revert|rm|stash|switch|tag|worktree'
GH_PR_WRITES='create|merge|close|edit|comment|review|checkout|ready|reopen'
GH_ISSUE_WRITES='create|edit|close|reopen|comment|delete|transfer|pin|unpin|lock|unlock|develop'
GH_WRITE_GROUPS='release|repo|workflow|auth'

WRITE="${S}git$GIT_OPTS$W($GIT_WRITES)$E|${S}gh$GH_OPTS$W(pr$W($GH_PR_WRITES)|issue$W($GH_ISSUE_WRITES)|$GH_WRITE_GROUPS)$E"

found=$(printf '%s\n' "$flat" | grep -oE "$WRITE" | head -n 1 | sed -e 's/^[^g]*//' -e 's/[^[:alnum:]_-]*$//' | tr -s ' ')
[ -z "$found" ] && exit 0

echo "Blocked: \`$found\` writes to git or GitHub. Agents in this repository run read-only git and gh commands only; ask the maintainer to run it (CLAUDE.md, Agent rules)." >&2
exit 2
