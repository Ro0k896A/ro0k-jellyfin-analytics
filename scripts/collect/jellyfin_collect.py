#!/usr/bin/env python3
"""Daily Jellyfin snapshot + activity log. Missing data -> null + errors entry.
Exit: 0 ok, 1 partial, 2 fatal (no key / cannot write)."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = os.environ.get("JF_URL", "http://localhost:8096")
KEYFILE = os.environ.get("JF_KEYFILE", "/srv/data/reports/.jellyfin-key")
OUT = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
errors = {}

try:
    TOKEN = open(KEYFILE).read().strip()
    assert TOKEN
except Exception as e:
    print(f"FATAL: cannot read API key at {KEYFILE}: {e}", file=sys.stderr); sys.exit(2)

def get(key, path, params=None):
    try:
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers={"Authorization": f'MediaBrowser Token="{TOKEN}"'})
        return json.load(urllib.request.urlopen(req, timeout=20))
    except Exception as e:
        errors[key] = str(e)[:200]
        return None

def main():
    now = datetime.now(ZoneInfo("America/New_York"))
    info = get("info", "/System/Info")
    counts = get("counts", "/Items/Counts")
    libs = get("libraries", "/Library/VirtualFolders")
    users = get("users", "/Users")
    sess = get("sessions", "/Sessions")
    since = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
    act = get("activity", "/System/ActivityLog/Entries", {"startIndex": 0, "limit": 1000, "minDate": since})

    playing = [s for s in sess if s.get("NowPlayingItem")] if isinstance(sess, list) else None
    snap = {
        "ts": now.isoformat(timespec="seconds"),
        "version": (info or {}).get("Version"),
        "counts": counts,
        "libraries": [{"name": l.get("Name"), "type": l.get("CollectionType")} for l in libs] if isinstance(libs, list) else None,
        "user_count": len(users) if isinstance(users, list) else None,
        "sessions_total": len(sess) if isinstance(sess, list) else None,
        "streams_active": len(playing) if playing is not None else None,
        "streams_transcoding": sum((s.get("PlayState") or {}).get("PlayMethod") == "Transcode" for s in playing) if playing is not None else None,
        "activity_entries_25h": len(act.get("Items", [])) if isinstance(act, dict) else None,
        "errors": errors,
    }
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"jellyfin-{now:%Y-%m-%d}.jsonl"), "a") as f:
            f.write(json.dumps(snap) + "\n")
        # Raw activity entries (deduplicate by id at analysis time; windows overlap by 1h)
        with open(os.path.join(OUT, f"jellyfin-activity-{now:%Y-%m-%d}.jsonl"), "a") as f:
            for e in (act or {}).get("Items", []):
                f.write(json.dumps({k: e.get(k) for k in ("Id", "Type", "Name", "Date", "UserId", "Severity")}) + "\n")
    except Exception as e:
        print(f"FATAL write: {e}", file=sys.stderr); return 2
    print(json.dumps(snap, indent=2))
    return 1 if errors else 0

sys.exit(main())
