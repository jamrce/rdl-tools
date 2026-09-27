#!/bin/sh
# Claude Code PreToolUse hook for Bash. Exits 2, which blocks the call, when git or gh appears
# anywhere in the command with a subcommand outside the read-only allowlist below:
# `git -C . commit`, `sh -c "git push"`, `a && git reset`, `git send-pack`, `gh api -X POST`.
#
# It greps the payload's `command` string with sed rather than parsing JSON, so it needs nothing
# beyond POSIX tools. A mention inside quoted text, such as `echo "git push"`, is blocked too. It
# stops habit, not an agent determined to hide a command, such as one decoded from base64 at run time.
set -u

payload=$(tr '\n' ' ')
command=$(printf '%s\n' "$payload" | sed -nE 's/.*"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')
# No `command` field found: scan the whole payload, so a format change fails closed.
[ -n "$command" ] || command=$payload

# JSON escapes, quotes, substitutions and separators become spaces, so a nested command reads as a plain one.
flat=$(printf '%s\n' "$command" | sed -e 's/\\[nrt]/ /g' -e "s/[\"'\`\$();|&<>{}\\\\]/ /g")

S='(^|[^[:alnum:]_.-])'
W='[[:space:]]+'
A='[^[:space:]]+'
# Global options allowed before the subcommand. `-c` is not one: it can define an alias for any write.
GIT_OPTS="($W(--no-pager|-P|--no-optional-locks|-C$W$A|--(git-dir|work-tree)(=|$W)$A))*"

GIT_READS='status|diff|log|show|rev-parse|ls-files|blame|grep|shortlog|describe|cat-file|ls-tree|rev-list|merge-base|show-ref|for-each-ref|name-rev|help|version|--version'
GH_READS='issue (view|list|status)|pr (view|list|diff|checks|status)|(search|api|help|--version|--help)( [^ ]+)?'

block() {
    echo "Blocked: \`$1\` is not a read-only git or gh command. Agents in this repository run read-only git and gh commands only; ask the maintainer to run it (CLAUDE.md, Agent rules)." >&2
    exit 2
}

# The token after `git` and its allowed options is the subcommand; anything unlisted, `-c` included, blocks.
printf '%s\n' "$flat" | grep -oE "${S}git$GIT_OPTS$W$A" | sed -e 's/^[^g]*//' | tr -s ' ' | while read -r found; do
    printf '%s\n' "${found##* }" | grep -qxE "$GIT_READS" || { echo "$found"; break; }
done | { read -r found && block "$found"; }
[ $? -eq 2 ] && exit 2

printf '%s\n' "$flat" | grep -oE "${S}gh$W$A($W$A)?" | sed -e 's/^[^g]*//' | tr -s ' ' | while read -r found; do
    printf '%s\n' "${found#gh }" | grep -qxE "$GH_READS" || { echo "$found"; break; }
done | { read -r found && block "$found"; }
[ $? -eq 2 ] && exit 2

# `gh api` is a read only as a GET: a non-GET method, or a field or body that implies POST, blocks.
if printf '%s\n' "$flat" | grep -qE "${S}gh${W}api$W"; then
    method=$(printf '%s\n' "$flat" | grep -oE "$W(-X|--method)(=|$W)?[[:alpha:]]+" | sed -e 's/.*[^[:alpha:]]//' | tr '[:lower:]' '[:upper:]' | grep -vx GET | head -n 1)
    [ -n "$method" ] && block "gh api $method"
    printf '%s\n' "$flat" | grep -qE "$W(-[fF]|--field|--raw-field|--input)(=|$W|[^[:space:]])" && block "gh api with a request body"
fi
exit 0
