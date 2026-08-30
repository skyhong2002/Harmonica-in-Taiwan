# Calendar Maintenance Job

`tw.observe.harmonica.calendar-maintenance` runs `scripts/sync_google_calendar_events.py`
once a day at 04:10 with a one-year lookback.

The LaunchAgent uses the system-Python-based
`~/.hermes/harmonica-intake-venv` through a login shell. Keep it aligned with
the main pipeline and submission intake jobs: Homebrew Python runtimes can be
killed by macOS code-signing enforcement after an in-place Homebrew upgrade.
The daily deep scan also selects the built-in REST client, whose requests have
a 30-second timeout, so a stalled Google client connection cannot hold the
maintenance lock indefinitely.

This is deliberately different from the sync step inside
`tw.observe.harmonica.pipeline`, which runs every 30 minutes. Both now scan a year
back so retained past events are found and updated instead of being inserted again.
The daily job remains responsible for a predictable 04:10 deep-maintenance pass.

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
~/.hermes/harmonica-intake-venv/bin/python scripts/sync_google_calendar_events.py --history-days 3650
```

The run summary reports `duplicate_deletions` separately, though it is also counted
inside `deleted`.

## Empty source guard

A sync whose source JSON has no events but whose calendar still holds managed events
reports `status: error` and deletes nothing, so a half-finished build cannot wipe the
public calendar. If the source genuinely ran dry, re-run with `--allow-empty`.
