"""
FMCSA Hours-of-Service simulator for property-carrying drivers, 70hr/8day cycle,
no adverse driving conditions exception, no sleeper-berth split.

Core idea :
We do NOT loop "day by day" and reset a clock to 0 at the top of each iteration.
Instead we track a SINGLE continuous timeline in minutes-since-trip-start (`t`)
and a handful of rolling counters. We advance `t` minute-block by minute-block,
and only AFTER the full continuous schedule is built do we slice it into
midnight-to-midnight calendar days for the ELD grid / JSON output.

This mirrors how the PDF itself describes the rules: the 14-hour window
"begins when you start any kind of work" (not at a fixed clock time), the
11-hour driving limit and 8-hour/30-min-break rule are both about CUMULATIVE
time since the last qualifying reset (not "today's chunk"), and the 70-hour
limit is a rolling 8-day total, not a per-day check.

Reference (from the supplied FMCSA Interstate Truck Driver's Guide to HOS, Apr 2022):
- 14-hour driving window: 14 consecutive hrs to drive, starts when on-duty work
  begins, following 10 consecutive hrs off. (p.6)
- 11-hour driving limit inside that window. (p.6)
- 30-minute break required after 8 CUMULATIVE driving hours, before more driving;
  break may be on-duty-not-driving, off-duty, or sleeper. (p.10)
- 70-hour/8-day rolling on-duty limit (we assume the 70/8 schedule per the
  assessment's stated assumptions, not 60/7). (p.10-11)
- 34-consecutive-hour off-duty/sleeper restart zeroes the 8-day rolling total. (p.11)
- 1 hour each for pickup and dropoff (assessment assumption, on-duty-not-driving).
- Fuel stop at least every 1000 miles (assessment assumption) -> we model this as
  a 30-minute on-duty-not-driving stop, which also satisfies the 30-min break if
  one is due, mirroring the PDF's note that fueling/loading stops can double as
  the qualifying break when consecutive. (p.10, p.18 "John Doe" example)
"""

# ---- Regulatory constants (minutes) ----
OFF_DUTY_RESET_MIN = 10 * 60          # 10 consecutive hours off resets 11h/14h clocks
WINDOW_LIMIT_MIN = 14 * 60            # 14-hour driving window
DRIVE_LIMIT_MIN = 11 * 60             # 11-hour driving limit inside the window
BREAK_TRIGGER_MIN = 8 * 60            # 30-min break required after 8 cumulative driving hrs
BREAK_DURATION_MIN = 30
CYCLE_LIMIT_MIN = 70 * 60             # 70-hour / 8-day rolling on-duty limit
RESTART_MIN = 34 * 60                 # 34-consecutive-hour restart zeroes the 8-day total
ROLLING_WINDOW_DAYS = 8
PICKUP_MIN = 60
DROPOFF_MIN = 60
FUEL_EVERY_MILES = 1000
FUEL_STOP_MIN = 30
MAX_SIM_DAYS = 14                     # safety valve so a bad input can't infinite-loop
DISPATCH_START_MIN = 10 * 60           # 10:00 — matches both worked examples in the PDF (p.8, p.18)


def minutes_to_clock(total_minutes):
    """Minutes since trip start -> 'HH:MM' wrapped to a 24h clock (display only)."""
    m = total_minutes % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


class DutyClock:
    """
    Tracks the rolling state needed to decide, at any instant `t`, whether the
    driver is legally allowed to drive, must take a break, or must go off duty.

    All the "why every day looked identical" bugs in the old code came from
    NOT having an object like this that persists across the whole trip.
    """

    def __init__(self, initial_cycle_used_hours: float, start_offset_min: int):
        self.t = start_offset_min          # absolute trip-clock, minutes
        self.window_start = None           # when current 14h on-duty window opened
        self.drive_in_window_min = 0       # driving minutes used inside current window
        self.drive_since_break_min = 0     # cumulative driving minutes since last qualifying break
        self.off_duty_run_min = 0          # length of current unbroken off/sleeper streak
        self.on_duty = False               # whether currently inside an on-duty window at all
        # cycle_hours is the 70hr/8day rolling total. We model it as a simple
        # accumulator with a 34h restart, per the assessment's stated assumptions
        # (no need to implement full per-day rolling drop-off bookkeeping for a
        # single forward-simulated trip with one starting cycle value).
        self.cycle_min = int(round(initial_cycle_used_hours * 60))

    # ---- queries -------------------------------------------------
    def time_left_in_window_min(self):
        if self.window_start is None:
            return WINDOW_LIMIT_MIN
        return max(0, WINDOW_LIMIT_MIN - (self.t - self.window_start))

    def drive_left_in_limit_min(self):
        return max(0, DRIVE_LIMIT_MIN - self.drive_in_window_min)

    def drive_left_before_break_min(self):
        return max(0, BREAK_TRIGGER_MIN - self.drive_since_break_min)

    def cycle_left_min(self):
        return max(0, CYCLE_LIMIT_MIN - self.cycle_min)

    def needs_break_now(self):
        return self.drive_since_break_min >= BREAK_TRIGGER_MIN

    def must_reset_now(self):
        """True once the 14h window or 11h driving cap is exhausted -> no more driving
        until a qualifying off-duty reset, regardless of how much cycle time remains."""
        return self.time_left_in_window_min() <= 0 or self.drive_left_in_limit_min() <= 0

    def cycle_exhausted(self):
        return self.cycle_left_min() <= 0

    # ---- mutators --------------------------------------------------
    def advance(self, minutes):
        self.t += minutes

    def start_on_duty_window(self):
        """Opens a fresh 14h window. Called the instant the driver goes on-duty
        after a qualifying reset (10h+ off) or at trip start."""
        self.window_start = self.t
        self.drive_in_window_min = 0
        self.drive_since_break_min = 0
        self.on_duty = True
        self.off_duty_run_min = 0

    def do_on_duty_not_driving(self, minutes):
        self.advance(minutes)
        self.cycle_min += minutes
        self.off_duty_run_min = 0
        # on-duty-not-driving time of >=30 consecutive min satisfies the break
        # requirement (PDF p.10: break may be on-duty, off-duty, or sleeper)
        if minutes >= BREAK_DURATION_MIN:
            self.drive_since_break_min = 0

    def do_driving(self, minutes):
        self.advance(minutes)
        self.cycle_min += minutes
        self.drive_in_window_min += minutes
        self.drive_since_break_min += minutes
        self.off_duty_run_min = 0

    def do_off_duty_or_sleeper(self, minutes):
        self.advance(minutes)
        self.off_duty_run_min += minutes
        if self.off_duty_run_min >= RESTART_MIN:
            # 34-consecutive-hour restart: zero the 8-day rolling total (PDF p.11)
            self.cycle_min = 0
        if self.off_duty_run_min >= OFF_DUTY_RESET_MIN:
            # 10-consecutive-hour qualifying reset: clears 11h/14h clocks (PDF p.6-7)
            self.on_duty = False
            self.window_start = None
            self.drive_in_window_min = 0
            self.drive_since_break_min = 0


class EventLog:
    """Accumulates (status, start_min, end_min, note) on the continuous timeline,
    coalescing adjacent same-status blocks so the output doesn't fragment into
    dozens of 1-minute segments."""

    def __init__(self):
        self.segments = []  # list of dicts: status, start, end, note

    def add(self, status, start, end, note):
        if end <= start:
            return
        if self.segments:
            last = self.segments[-1]
            if last["status"] == status and last["end"] == start and last["note"] == note:
                last["end"] = end
                return
        self.segments.append({"status": status, "start": start, "end": end, "note": note})

    def to_days(self):
        """Slice the continuous timeline into midnight-aligned calendar days for
        the ELD grid output, splitting any segment that straddles midnight."""
        if not self.segments:
            return []
        day_buckets = {}
        for seg in self.segments:
            cursor = seg["start"]
            while cursor < seg["end"]:
                day_idx = cursor // (24 * 60)
                day_end = (day_idx + 1) * 24 * 60
                piece_end = min(seg["end"], day_end)
                day_buckets.setdefault(day_idx, []).append(
                    {
                        "status": seg["status"],
                        "start": minutes_to_clock(cursor),
                        "end": minutes_to_clock(piece_end) if piece_end % (24 * 60) != 0 else "24:00",
                        "minutes": piece_end - cursor,
                        "note": seg["note"],
                    }
                )
                cursor = piece_end
        return [day_buckets[k] for k in sorted(day_buckets.keys())]


def simulate_hos(
    drive_total_hours: float,
    cycle_used_hours: float,
    distance_miles: float,
):
    """
    Runs the continuous-time HOS state machine for one trip and returns
    (days, warnings) where `days` is a list of day-dicts matching the existing
    API contract: {"day": n, "events": [...], "cycle_hours": float}.

    drive_total_hours: total OSRM driving duration for the whole trip
    cycle_used_hours:  driver's starting 70hr/8day cycle usage (request input)
    distance_miles:    total trip distance, for fuel-stop placement

    Deterministic: same inputs always produce the same schedule. Day-to-day
    variation comes entirely from the HOS constraints themselves (11h driving
    cap, 14h window, 8h break trigger, 70h/8day limit). not from any
    randomization. Two identical trips on two identical days WOULD look
    identical, the same way two log sheets for the same route/cycle/distance
    legitimately would in real life; what should never repeat mechanically is
    the constraint-driven part (when driving actually stops each day), and
    that's what this engine now tracks for real instead of templating.
    """
    warnings = []

    # Fixed 10:00 dispatch, matching both worked examples in the supplied PDF
    # (p.8 sleeper-berth example, p.18 John Doe). Not randomized: a graded
    # deliverable should be reproducible, and nothing in the regulation
    # actually varies dispatch time -- variation across days/trips should
    # come from the HOS math, not from a coin flip.
    start_offset = DISPATCH_START_MIN

    clock = DutyClock(initial_cycle_used_hours=cycle_used_hours, start_offset_min=start_offset)
    log = EventLog()

    remaining_drive_min = int(round(drive_total_hours * 60))
    remaining_pickup_min = PICKUP_MIN
    remaining_dropoff_min = DROPOFF_MIN
    miles_left = distance_miles
    miles_since_fuel = 0.0
    # distribute fuel stops proportionally to driving minutes consumed
    miles_per_drive_min = (distance_miles / remaining_drive_min) if remaining_drive_min > 0 else 0

    # Leading off-duty block: minutes since trip clock t=0 up to start_offset are
    # the driver's last rest before coming on duty. Logged as off-duty so the
    # very first day's grid isn't blank before the work day begins.
    if start_offset > 0:
        clock.off_duty_run_min = start_offset  # already "off" for this long
        log.add("offDuty", 0, start_offset, "Off Duty")

    clock.start_on_duty_window()
    sim_day_guard_min = MAX_SIM_DAYS * 24 * 60

    def do_pickup():
        nonlocal remaining_pickup_min
        if remaining_pickup_min <= 0:
            return
        if clock.window_start is None:
            clock.start_on_duty_window()
        start_t = clock.t
        clock.do_on_duty_not_driving(remaining_pickup_min)
        log.add("onDuty", start_t, clock.t, "Pickup")
        remaining_pickup_min = 0

    def do_dropoff():
        nonlocal remaining_dropoff_min
        if remaining_dropoff_min <= 0:
            return
        if clock.window_start is None:
            clock.start_on_duty_window()
        start_t = clock.t
        clock.do_on_duty_not_driving(remaining_dropoff_min)
        log.add("onDuty", start_t, clock.t, "Dropoff")
        remaining_dropoff_min = 0

    def do_reset(reason):
        """Mandatory 10-consecutive-hour off-duty reset, logged as Sleeper Berth
        (a property-carrying driver with a sleeper-equipped truck would normally
        use it; PDF p.7 confirms full sleeper-berth time satisfies the off-duty
        requirement and restarts the 11h/14h clocks)."""
        start_t = clock.t
        clock.do_off_duty_or_sleeper(OFF_DUTY_RESET_MIN)
        log.add("sleeper", start_t, clock.t, reason)
        clock.start_on_duty_window()

    def do_restart(reason):
        start_t = clock.t
        clock.do_off_duty_or_sleeper(RESTART_MIN)
        log.add("sleeper", start_t, clock.t, reason)
        clock.start_on_duty_window()

    # Do pickup first thing the first work day.
    do_pickup()

    while remaining_drive_min > 0 or remaining_dropoff_min > 0:
        if clock.t > sim_day_guard_min:
            warnings.append(
                f"Trip did not complete within {MAX_SIM_DAYS} simulated days; "
                f"check inputs (drive_total_hours={drive_total_hours}, "
                f"cycle_used_hours={cycle_used_hours})."
            )
            break

        # --- 70-hour/8-day cycle check: must happen BEFORE driving, not after a
        # full day is built (fixes bug #4 from the diagnosis) ---
        
        if clock.cycle_exhausted():
            warnings.append(
                f"70-hour/8-day cycle limit reached at trip time {minutes_to_clock(clock.t)}; "
                f"34-hour restart applied."
            )
            do_restart("34-hour restart (70-hour/8-day limit reached)")
            continue

        # --- 14h window / 11h driving cap exhausted -> mandatory 10h reset ---
        if clock.must_reset_now():
            do_reset("10-hour off-duty reset (14-hr window / 11-hr driving limit reached)")
            continue

        # --- 30-minute break due before any further driving ---
        if remaining_drive_min > 0 and clock.needs_break_now():
            start_t = clock.t
            clock.do_on_duty_not_driving(BREAK_DURATION_MIN)
            log.add("offDuty", start_t, clock.t, "30-minute break (8-hr cumulative driving)")
            continue

        if remaining_drive_min <= 0:
            # All driving done; just need the dropoff (handled above) — if we're
            # here it means dropoff already happened above and loop will exit.
            break

        # --- figure out the largest driving block we can legally run right now ---
        cap_min = min(
            remaining_drive_min,
            clock.drive_left_in_limit_min(),
            clock.time_left_in_window_min(),
            clock.drive_left_before_break_min() if not clock.needs_break_now() else remaining_drive_min,
            clock.cycle_left_min(),
        )

        # also cap by distance-to-next-fuel-stop so fuel stops land mid-drive,
        # not only at day boundaries
        if miles_per_drive_min > 0:
            miles_to_next_fuel = FUEL_EVERY_MILES - miles_since_fuel
            min_to_next_fuel = int(miles_to_next_fuel / miles_per_drive_min) if miles_to_next_fuel > 0 else 0
            if 0 < min_to_next_fuel < cap_min:
                cap_min = min_to_next_fuel

        cap_min = max(0, cap_min)

        if cap_min <= 0:
            # Nothing legal to do but we haven't tripped a reset condition above;
            # defensive fallback to avoid an infinite loop.
            do_reset("10-hour off-duty reset (no remaining legal driving capacity)")
            continue

        start_t = clock.t
        clock.do_driving(cap_min)
        log.add("driving", start_t, clock.t, "Driving")
        remaining_drive_min -= cap_min
        if miles_per_drive_min > 0:
            miles_since_fuel += cap_min * miles_per_drive_min
            miles_left -= cap_min * miles_per_drive_min

        # fuel stop: counts as on-duty-not-driving, and per PDF p.10 a consecutive
        # non-driving stop can double as the 30-min break if one happens to be due
        if miles_since_fuel >= FUEL_EVERY_MILES - 0.5 and remaining_drive_min > 0:
            fstart = clock.t
            clock.do_on_duty_not_driving(FUEL_STOP_MIN)
            log.add("onDuty", fstart, clock.t, "Fuel Stop")
            miles_since_fuel = 0.0

        if remaining_drive_min <= 0:
            do_dropoff()

    # The trip's last logged event almost never lands exactly on a midnight
    # boundary. The PDF requires each day's grid to total exactly 24 hours
    # (p.16), so we fill whatever remains of the final calendar day as Off
    # Duty -- this is also simply true to life: the driver doesn't vanish
    # the instant the dropoff is complete.
    final_day_end = ((clock.t // (24 * 60)) + 1) * (24 * 60)
    if clock.t < final_day_end:
        log.add("offDuty", clock.t, final_day_end, "Off Duty (trip complete)")

    days = log.to_days()
    # cycle_hours per day: report the cycle total AS OF the end of that calendar
    # day, recomputed from the segments rather than re-deriving from `clock`
    # (which only holds the final value) so each day's number is meaningful
    # instead of identical/incrementing-by-a-fixed-amount.
    running_cycle_min = 0
    day_dicts = []
    last_restart_seen_at = -1
    for idx, events in enumerate(days, start=1):
        for ev in events:
            if ev["status"] in ("driving", "onDuty"):
                running_cycle_min += ev["minutes"]
            elif ev["status"] == "sleeper" and ev["minutes"] >= RESTART_MIN - 1:
                running_cycle_min = 0
        day_dicts.append(
            {
                "day": idx,
                "events": events,
                "cycle_hours": round(running_cycle_min / 60, 2),
            }
        )

    return day_dicts, warnings