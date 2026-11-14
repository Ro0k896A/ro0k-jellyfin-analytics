# Jellyfin Analytics

Daily collection and monthly/quarterly analysis for the homelab Jellyfin server.

- `scripts/collect/`: daily snapshot and activity-log collector (raw data stays on the server)
- `scripts/report/`: aggregate-only Markdown reports (no usernames or titles)
- `scripts/publish/`: guarded publisher (clean repo, fast-forward only, sanitization gate)
- `reports/monthly|quarterly/`: published reports

Weekly reports are intentionally skipped.
