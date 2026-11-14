#!/bin/bash
# Usage: publish.sh monthly|quarterly   (DRY_RUN=1 to skip commit/push)
# Run as adminro0k, never root. Exit: 0 ok/nothing to do, 1 refused (unsafe state),
# 2 generation failed, 3 skipped (already running), 4 git failure.
P=${1:?usage: publish.sh monthly|quarterly}
case $P in monthly|quarterly) ;; *) echo "bad period" >&2; exit 1 ;; esac
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOG=/srv/data/reports/logs/jellyfin-publish.log
log() { echo "$(date -Is) [$P] $*" >> "$LOG"; }
die() { log "REFUSED/FAILED: $2"; echo "$2" >&2; exit "$1"; }

[ "$(id -u)" -ne 0 ] || die 1 "do not run as root"
exec 9>/tmp/jf-publish.lock
flock -n 9 || { log "SKIP: already running"; exit 3; }
cd "$REPO" || die 1 "repo missing"

[ "$(git remote get-url origin)" = "git@github.com:Ro0k896A/ro0k-jellyfin-analytics.git" ] || die 1 "unexpected remote"
[ "$(git branch --show-current)" = main ] || die 1 "not on main"
[ -z "$(git status --porcelain)" ] || die 1 "repo not clean; refusing to commit"
git config user.name >/dev/null && git config user.email >/dev/null || die 1 "git identity not set"
git pull --ff-only -q origin main 2>>"$LOG" || die 4 "pull --ff-only failed (diverged or network)"

OUT=$("$REPO/scripts/report/jf_report.py" "$P" 2>>"$LOG") || die 2 "report generation failed (no data?)"
REL=${OUT#"$REPO"/}

# Sanitization gate: refuse to publish anything resembling a secret or an IP address
if grep -I -n -i -E 'password|passwd|secret|token|api[_-]?key|BEGIN [A-Z ]*PRIVATE|([0-9]{1,3}\.){3}[0-9]{1,3}' "$OUT" >>"$LOG"; then
  rm -f "$OUT"; die 1 "sanitization gate tripped (see log); report discarded"
fi

if [ -n "$DRY_RUN" ]; then log "DRY_RUN ok: $REL"; echo "DRY RUN: would publish $REL"; rm -f "$OUT"; exit 0; fi

git add -- "$REL"
if git diff --cached --quiet; then log "nothing to commit"; exit 0; fi
git commit -q -m "Add $P report $(date +%F)" 2>>"$LOG" || die 4 "commit failed"
git push -q origin main 2>>"$LOG" || die 4 "push failed (not forced; commit stays local)"
log "PUBLISHED $REL"
