"""4.86: the team's calendar as an iCalendar feed (RFC 5545), the standard every calendar app subscribes to: Apple
Calendar (iPhone, Mac), Google Calendar, Outlook, Proton, Thunderbird, the Android calendar apps. One event per
practice and match day; the times are in UTC, so every app shows them in its own time zone."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

PRODID = "-//Nexus//Team calendar//EN"


def esc(s: str) -> str:
    return (str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", ""))


def fold(line: str) -> list[str]:
    """Lines longer than 75 octets go on in lines that start with a space (RFC 5545 3.1), not inside a character."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return [out[0]] + [" " + x for x in out[1:]]


def utc(local: datetime) -> str:
    """A naive local time (the server's clock) -> 20261203T190000Z."""
    return local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def events(start: date, days: int, practice: dict | None, match: dict | None, map_on=None, team: str = "") -> list[dict]:
    """practice: {days: [weekday], time: "HH:MM", minutes} or None; match: {days, time, minutes} or None; map_on(day) ->
    (map, playoffs). -> [{uid, start, end, title, text}] (naive local datetimes) from start for `days` days."""
    out = []
    for k in range(days):
        d = start + timedelta(days=k)
        for kind, cfg in (("practice", practice), ("match", match)):
            if not cfg or d.weekday() not in (cfg.get("days") or []):
                continue
            try:
                hh, mm = (int(x) for x in str(cfg.get("time") or "").split(":"))
            except ValueError:
                continue
            st = datetime(d.year, d.month, d.day, hh, mm)
            en = st + timedelta(minutes=int(cfg.get("minutes") or 60))
            if kind == "practice":
                title, text = f"🏋️ {team} practice".strip(), "The plan for the day is on the team's Practice page in Nexus."
            else:
                m, po = map_on(d) if map_on else (None, False)
                title = f"🏆 {team} {'playoffs' if po else 'match'}".strip() + (f": {m}" if m else "")
                text = (f"Premier {'playoffs' if po else 'match'}" + (f" on {m}" if m else "") +
                        ". Mark if you can play under Premier › Availability; the match screen has the comp, strats and lineups.")
            out.append({"uid": f"{kind}-{d.isoformat()}", "start": st, "end": en, "title": title, "text": text})
    return out


def ics(evts: list[dict], name: str, uid_base: str, now: datetime | None = None, url: str = "") -> str:
    now = now or datetime.now()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{esc(name)}", "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    stamp = utc(now)
    for e in evts:
        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}-{uid_base}@nexus", f"DTSTAMP:{stamp}", f"DTSTART:{utc(e['start'])}",
                  f"DTEND:{utc(e['end'])}", f"SUMMARY:{esc(e['title'])}", f"DESCRIPTION:{esc(e['text'])}"]
        if url:
            lines.append(f"URL:{url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(x for line in lines for x in fold(line)) + "\r\n"
