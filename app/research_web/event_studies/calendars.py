"""Fixed calendar/event windows over explicit exchange sessions only."""

from bisect import bisect_left, bisect_right
from datetime import date

from .contracts import StudyError, stamp

CALENDAR_RULES = tuple(
    [f"holiday_{side}_{n}" for side in ("pre", "post") for n in (1, 5, 10)]
    + ["holiday_episode", "reopening_gap"]
    + [f"weekday_{day}_{n}" for day in range(5) for n in (1, 5)]
    + [
        f"{period}_{side}_{n}"
        for period in ("month", "quarter", "year")
        for side in ("start", "end")
        for n in (1, 5)
    ]
)
EVENT_RULES = ("event_pre_5", "event_pre_10", "event_during", "event_post_5", "event_post_10")
FAMILIES = {
    "holiday": tuple(
        rule for rule in CALENDAR_RULES if rule.startswith("holiday_") or rule == "reopening_gap"
    ),
    "weekday": tuple(rule for rule in CALENDAR_RULES if rule.startswith("weekday_")),
    **{
        f"{period}_{side}": tuple(
            rule for rule in CALENDAR_RULES if rule.startswith(f"{period}_{side}_")
        )
        for period in ("month", "quarter", "year")
        for side in ("start", "end")
    },
    **{
        category: EVENT_RULES
        for category in (
            "macro",
            "policy",
            "geopolitics",
            "war",
            "sports",
            "disaster",
            "unexpected",
            "other",
        )
    },
}


def calendar_knowledge_gaps(calendar, window, known_by=None):
    """Require published boundary sessions; capture timestamps grant no PIT proof."""
    days = {session.day.isoformat(): i for i, session in enumerate(calendar.sessions)}
    if window["start"] not in days or window["end"] not in days:
        return ["calendar_window_boundary_missing"]
    first, last = days[window["start"]], days[window["end"]]
    cutoff = stamp(known_by) if known_by is not None else calendar.sessions[first].closes
    for session in calendar.sessions[first : min(len(days), last + 2)]:
        known = session.known_at or calendar.announcement_known_at
        reference = session.announcement_version_ref or calendar.announcement_version_ref
        if known is None or not reference or stamp(known) > cutoff:
            return ["calendar_boundary_not_known_at_signal"]
    return []


def _window(sessions, start, end, rule, episode, *, price_field="close"):
    if start < 0 or end >= len(sessions) or start > end:
        return None
    return {
        "rule": rule,
        "episode": episode,
        "start": sessions[start].day.isoformat(),
        "end": sessions[end].day.isoformat(),
        "start_price": "close",
        "end_price": price_field,
        "overlapping_episodes": [],
    }


def annotate_overlaps(windows):
    active, overlaps = [], [set() for _ in windows]
    for i in sorted(range(len(windows)), key=lambda k: windows[k]["start"]):
        row = windows[i]
        active = [j for j in active if windows[j]["end"] >= row["start"]]
        for j in active:
            if windows[j]["episode"] != row["episode"]:
                overlaps[i].add(windows[j]["episode"])
                overlaps[j].add(row["episode"])
        active.append(i)
    for i, row in enumerate(windows):
        row["overlapping_episodes"] = sorted(overlaps[i])
    return windows


def _episodes(calendar, events, prefix, lengths):
    sessions = calendar.sessions
    days = [s.day for s in sessions]
    result = []
    for event in events:
        try:
            start = date.fromisoformat(event["start"])
            unknown_end = event.get("end_known") is False or (
                event.get("lifecycle") == "ongoing" and not event.get("end")
            )
            end = None if unknown_end else date.fromisoformat(event["end"])
            episode = event["id"]
            if (end is not None and start > end) or not isinstance(episode, str):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise StudyError("event_dates_invalid") from None
        before = bisect_left(days, start) - 1
        final = bisect_right(days, end) - 1 if end is not None else None
        if prefix == "holiday" and end is not None and any(start <= day <= end for day in days):
            raise StudyError("holiday_overlaps_session")
        definitions = []
        for n in lengths:
            definitions.append((before - n, before, f"{prefix}_pre_{n}", "close"))
            if final is not None:
                definitions.append((final, final + n, f"{prefix}_post_{n}", "close"))
        if prefix == "holiday" and final is not None:
            definitions.extend(
                [
                    (before, final + 1, "holiday_episode", "close"),
                    (before, final + 1, "reopening_gap", "open"),
                ]
            )
        elif prefix != "holiday" and final is not None:
            definitions.append((before, final, "event_during", "close"))
        for first, last, rule, field in definitions:
            row = _window(sessions, first, last, rule, episode, price_field=field)
            if row:
                row["event_end_known"] = not unknown_end
                result.append(row)
    return result


def event_windows(calendar, events):
    return annotate_overlaps(_episodes(calendar, events, "event", (5, 10)))


def calendar_windows(calendar, holidays=()):
    sessions = calendar.sessions
    result = _episodes(calendar, holidays, "holiday", (1, 5, 10))
    for i, session in enumerate(sessions):
        for n in (1, 5):
            row = _window(
                sessions, i - n, i, f"weekday_{session.day.weekday()}_{n}", f"weekday:{session.day}"
            )
            if row:
                result.append(row)
        # Boundary membership uses actual neighbouring sessions, never invented weekdays.
        if i == 0 or i == len(sessions) - 1:
            continue
        previous, following = sessions[i - 1].day, sessions[i + 1].day
        for period, key in (
            ("month", lambda d: (d.year, d.month)),
            ("quarter", lambda d: (d.year, (d.month - 1) // 3)),
            ("year", lambda d: d.year),
        ):
            if key(following) != key(session.day):
                for n in (1, 5):
                    row = _window(
                        sessions, i - n, i, f"{period}_end_{n}", f"{period}:{key(session.day)}"
                    )
                    if row:
                        result.append(row)
            if key(previous) != key(session.day):
                for n in (1, 5):
                    row = _window(
                        sessions,
                        i - 1,
                        i + n - 1,
                        f"{period}_start_{n}",
                        f"{period}:{key(session.day)}",
                    )
                    if row:
                        result.append(row)
    return annotate_overlaps(result)
