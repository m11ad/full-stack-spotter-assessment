"""
Independent HOS compliance validator.

This deliberately does NOT reuse any state from hos_engine.DutyClock ; it
re-derives compliance purely from the emitted event list, the same way an
auditor or roadside inspector would read a printed log. If hos_engine.py has
a subtle bug, this script is written from scratch against the PDF text so it
won't share the bug.

Checks implemented, each tied to a PDF citation:
1. 11-hour driving limit per on-duty window (p.6)
2. 14-hour window limit : no driving once 14h have elapsed since window open (p.6)
3. 30-min break required after 8 CUMULATIVE driving hours since last break (p.10)
4. 10-consecutive-hour off/sleeper required between on-duty windows (p.6-7)
5. 70-hour/8-day rolling on-duty total never exceeded without a 34h restart (p.10-11)
6. Every 24h calendar day's logged minutes sum to exactly 1440 (p.16, "must equal 24 hours")
"""

import sys
from hos_engine import simulate_hos


def flatten_to_continuous(days):
    """Re-stitch the per-day sliced events back into one continuous timeline of
    (status, start_abs_min, end_abs_min, note) tuples, undoing the midnight
    slicing hos_engine.EventLog.to_days() does, so we can check windows that
    span midnight."""
    flat = []
    for day_idx, day in enumerate(days):
        day_offset = day_idx * 24 * 60
        for ev in day["events"]:
            h, m = map(int, ev["start"].split(":"))
            start_local = h * 60 + m
            if ev["end"] == "24:00":
                end_local = 24 * 60
            else:
                h2, m2 = map(int, ev["end"].split(":"))
                end_local = h2 * 60 + m2
            flat.append(
                (ev["status"], day_offset + start_local, day_offset + end_local, ev["note"])
            )
    # merge adjacent same-status/note segments split only by the midnight slice
    merged = []
    for seg in flat:
        if merged and merged[-1][0] == seg[0] and merged[-1][2] == seg[1] and merged[-1][3] == seg[3]:
            merged[-1] = (merged[-1][0], merged[-1][1], seg[2], merged[-1][3])
        else:
            merged.append(list(seg))
    return [tuple(x) for x in merged]


def validate(days, label=""):
    violations = []
    timeline = flatten_to_continuous(days)

    # --- Check 6: each calendar day sums to 1440 ---
    for idx, day in enumerate(days, start=1):
        total = sum(ev["minutes"] for ev in day["events"])
        if total != 1440:
            violations.append(f"Day {idx}: events sum to {total} min, expected 1440")

    # --- Walk the continuous timeline maintaining the same four counters an
    # auditor would, independently of hos_engine's internals ---
    window_start = None
    drive_in_window = 0
    drive_since_break = 0
    off_run = 0
    cycle_min = 0
    t_cursor = 0
    just_had_qualifying_reset = True  # trip start counts as a valid place to open a window
    prev_status = None

    for status, start, end, note in timeline:
        gap = start - t_cursor
        if gap > 0:
            violations.append(f"Gap in timeline: {gap} unaccounted minutes before t={start}")
        dur = end - start
        t_cursor = end

        if status == "driving":
            if window_start is None:
                if not just_had_qualifying_reset:
                    violations.append(
                        f"t={start}: new on-duty window opened by driving, but the prior "
                        f"off-duty/sleeper stretch was only {off_run}min (<600min) -- "
                        f"driving resumed WITHOUT a qualifying 10-hour reset"
                    )
                window_start = start
                drive_in_window = 0
                drive_since_break = 0
            elapsed_in_window = start - window_start
            if elapsed_in_window >= 14 * 60:
                violations.append(
                    f"t={start}: driving started at {elapsed_in_window}min into on-duty window "
                    f"(>=14h={14*60}min) -- 14-HOUR WINDOW VIOLATION"
                )
            if drive_in_window >= 11 * 60:
                violations.append(
                    f"t={start}: driving resumed with {drive_in_window}min already driven "
                    f"in this window (>=11h={11*60}min) -- 11-HOUR LIMIT VIOLATION"
                )
            if drive_since_break >= 8 * 60:
                violations.append(
                    f"t={start}: driving resumed with {drive_since_break}min cumulative "
                    f"since last break (>=8h={8*60}min, needs 30-min break) -- BREAK RULE VIOLATION"
                )
            drive_in_window += dur
            drive_since_break += dur
            cycle_min += dur
            off_run = 0

        elif status == "onDuty":
            if window_start is None:
                if not just_had_qualifying_reset:
                    violations.append(
                        f"t={start}: new on-duty window opened by on-duty-not-driving, but the "
                        f"prior off-duty/sleeper stretch was only {off_run}min (<600min)"
                    )
                window_start = start
            cycle_min += dur
            if dur >= 30:
                drive_since_break = 0
            off_run = 0

        elif status in ("offDuty", "sleeper"):
            off_run += dur
            if dur >= 30:
                drive_since_break = 0
            if off_run >= 34 * 60:
                cycle_min = 0
            if off_run >= 10 * 60:
                window_start = None
                drive_in_window = 0
                drive_since_break = 0
                just_had_qualifying_reset = True
            else:
                just_had_qualifying_reset = False

        if cycle_min > 70 * 60:
            violations.append(
                f"t={end}: cycle total {cycle_min}min ({cycle_min/60:.1f}h) exceeds 70h "
                f"-- 70-HOUR/8-DAY LIMIT VIOLATION"
            )

    print(f"=== Validation: {label} ===")
    if violations:
        print(f"FOUND {len(violations)} VIOLATION(S):")
        for v in violations:
            print(f"  - {v}")
    else:
        print("No violations found. Compliant.")
    print()
    return violations


if __name__ == "__main__":
    test_cases = [
        dict(drive_total_hours=50.2, cycle_used_hours=0, distance_miles=2812.84),
        dict(drive_total_hours=8.5, cycle_used_hours=0, distance_miles=450),
        dict(drive_total_hours=10.9, cycle_used_hours=0, distance_miles=600),
        dict(drive_total_hours=11.1, cycle_used_hours=0, distance_miles=610),
        dict(drive_total_hours=120, cycle_used_hours=0, distance_miles=6500),
        dict(drive_total_hours=20, cycle_used_hours=65, distance_miles=1100),
        dict(drive_total_hours=5, cycle_used_hours=69.5, distance_miles=200),
        dict(drive_total_hours=11.0, cycle_used_hours=0, distance_miles=600),
        dict(drive_total_hours=22.0, cycle_used_hours=0, distance_miles=1200),
        dict(drive_total_hours=14.0, cycle_used_hours=0, distance_miles=750),
    ]

    total_violations = 0
    for i, kwargs in enumerate(test_cases):
        days, warnings = simulate_hos(**kwargs)
        label = f"case {i+1}: {kwargs}"
        v = validate(days, label=label)
        total_violations += len(v)
        if warnings:
            print(f"  (engine warnings: {warnings})\n")

    print(f"TOTAL VIOLATIONS ACROSS ALL CASES: {total_violations}")
    sys.exit(1 if total_violations else 0)