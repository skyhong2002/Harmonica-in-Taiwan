# Calendar Maintenance Job

`tw.observe.harmonica.calendar-maintenance` runs `scripts/sync_google_calendar_events.py`
once a day at 04:10 with a one-year lookback.

This is deliberately different from the sync step inside
`tw.observe.harmonica.pipeline`, which runs every 30 minutes with the default 7-day
lookback. The short window keeps the routine sync cheap, but it also means duplicate
copies of an event older than a week are never seen again. The daily job scans a year
back so those get collapsed to a single copy.

Both jobs take an exclusive lock on `state/google-calendar-sync.lock`. The lock is
non-blocking: whichever run starts second reports `status: skipped` and exits 0 rather
than queueing. Missing one maintenance pass is harmless; a queue of runs blocked behind
a stuck Google API call is not.

## Load

```sh
cp deploy/tw.observe.harmonica.calendar-maintenance.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/tw.observe.harmonica.calendar-maintenance.plist
```

Logs land in `~/Library/Logs/Harmonica-in-Taiwan/calendar-maintenance{,.err}.log`.

## One-off deep clean

```sh
~/.hermes/google-workspace-venv/bin/python scripts/sync_google_calendar_events.py --history-days 3650
```

The run summary reports `duplicate_deletions` separately, though it is also counted
inside `deleted`.

## Empty source guard

A sync whose source JSON has no events but whose calendar still holds managed events
reports `status: error` and deletes nothing, so a half-finished build cannot wipe the
public calendar. If the source genuinely ran dry, re-run with `--allow-empty`.
