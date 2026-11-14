#!/usr/bin/env python3
"""Aggregate Jellyfin raw data into Markdown. No usernames/titles. Usage: jf_report.py monthly|quarterly
Missing data -> n/a, never 0. Exit: 0 ok, 1 no data."""
import collections, glob, json, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DAYS = {"monthly": 31, "quarterly": 92}
RAW = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
period = sys.argv[1] if len(sys.argv) > 1 else ""
if period not in DAYS:
    print("usage: jf_report.py monthly|quarterly", file=sys.stderr); sys.exit(1)
now = datetime.now(ZoneInfo("America/New_York")); cut = now - timedelta(days=DAYS[period])

def rows(pattern):
    for p in sorted(glob.glob(os.path.join(RAW, pattern))):
        for line in open(p):
            try: yield json.loads(line)
            except Exception: continue

snaps = [r for r in rows("jellyfin-[0-9]*.jsonl") if datetime.fromisoformat(r["ts"]) >= cut]
seen, acts = set(), []
for r in rows("jellyfin-activity-*.jsonl"):
    if r.get("Id") in seen or not r.get("Date"): continue
    if datetime.fromisoformat(r["Date"][:19]).replace(tzinfo=ZoneInfo("UTC")) >= cut:
        seen.add(r["Id"]); acts.append(r)
if not (snaps or acts):
    print(f"No Jellyfin data for the last {DAYS[period]} days", file=sys.stderr); sys.exit(1)

L = [f"# Jellyfin {period.capitalize()} Analytics", "",
     f"Generated {now:%Y-%m-%d %H:%M %Z} | window: last {DAYS[period]} days | daily snapshots: {len(snaps)} | activity events: {len(acts)}", ""]

L += ["## Library size", ""]
good = [s for s in snaps if isinstance(s.get("counts"), dict)]
if good:
    a, b = good[0]["counts"], good[-1]["counts"]
    L += ["| Item type | First | Latest | Change |", "|---|---|---|---|"]
    for k in sorted(b):
        if isinstance(b[k], int) and b[k] > 0 or isinstance(a.get(k), int) and a[k] > 0:
            x, y = a.get(k), b.get(k)
            L.append(f"| {k.replace('Count','')} | {x if x is not None else 'n/a'} | {y if y is not None else 'n/a'} | {y-x if None not in (x,y) else 'n/a'} |")
else:
    L.append("No library count data.")

L += ["", "## Streaming (sampled once per day, so peaks are lower bounds)", ""]
st = [s for s in snaps if s.get("streams_active") is not None]
L.append(f"- Snapshots with stream data: {len(st)} of {len(snaps)}")
if st:
    L.append(f"- Max concurrent streams seen: {max(s['streams_active'] for s in st)}; "
             f"snapshots with any transcoding: {sum(1 for s in st if (s.get('streams_transcoding') or 0) > 0)}")
us = [s["user_count"] for s in snaps if s.get("user_count") is not None]
L.append(f"- Registered users (latest): {us[-1] if us else 'n/a'}")
L.append(f"- Server version (latest): {next((s['version'] for s in reversed(snaps) if s.get('version')), 'n/a')}")

L += ["", "## Activity log", ""]
if acts:
    types = collections.Counter((a.get("Type") or "unknown").replace("Password", "Credential") for a in acts)
    L += ["| Event type | Count |", "|---|---|"] + [f"| {t} | {n} |" for t, n in types.most_common(12)]
    plays = [a for a in acts if (a.get("Type") or "").endswith("Playback")]
    wk = collections.Counter(datetime.fromisoformat(a["Date"][:10]).strftime("%G-W%V") for a in plays)
    L += ["", f"- Playback starts: {len(plays)} | distinct active users: {len({a.get('UserId') for a in plays if a.get('UserId')})}",
          f"- Auth failures: {sum(1 for a in acts if 'AuthenticationFailed' in (a.get('Type') or ''))}",
          f"- Warning/error severity events: {sum(1 for a in acts if a.get('Severity') in ('Warning','Error','Critical'))}"]
    if wk: L += ["", "| ISO week (UTC) | Playback starts |", "|---|---|"] + [f"| {w} | {n} |" for w, n in sorted(wk.items())]
else:
    L.append("No activity data.")
L += ["", "## Notes", "", "- No Playback Reporting plugin installed: watch duration and per-title history are not collected.",
      "- Aggregates only; usernames and titles stay on the server."]

out = os.path.join(REPO, "reports", period); os.makedirs(out, exist_ok=True)
path = os.path.join(out, f"{period}-{now:%Y-%m-%d}.md"); open(path, "w").write("\n".join(L) + "\n"); print(path)
