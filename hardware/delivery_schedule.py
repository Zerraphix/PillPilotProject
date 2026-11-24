"""Tid fra Raspberry Pi's HTTP Date-header; ingen internet/NTP noedvendig.

Ingen motor- eller sensorhandlinger. Alle tider sammenlignes i UTC.
"""
from time import ticks_ms, ticks_diff
import config
from pillpilot_api import get_udleveringer
from delivery_status import FEJL, set_udleveringsstatus

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _seconds(y, m, d, h, minute, s):
    if not 2000 <= y <= 2099 or not 1 <= m <= 12:
        raise ValueError("Ugyldigt aar/maaned")
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    lengths = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not (1 <= d <= lengths[m-1] and 0 <= h <= 23 and 0 <= minute <= 59 and 0 <= s <= 59):
        raise ValueError("Ugyldig dato/tid")
    prev = y - 1
    days = 365 * (y - 2000) + (prev//4 - 1999//4) - (prev//100 - 1999//100) + (prev//400 - 1999//400)
    return (days + sum(lengths[:m-1]) + d - 1) * 86400 + h * 3600 + minute * 60 + s


def parse_iso(value):
    """ISO 8601 med eksplicit offset eller Z; millisekunder siden 2000 UTC."""
    if (not isinstance(value, str) or len(value) < 20 or value[4] != "-"
            or value[7] != "-" or value[10] not in ("T", " ")
            or value[13] != ":" or value[16] != ":"):
        raise ValueError("Ugyldigt planlagt_tid")
    sec = _seconds(int(value[:4]), int(value[5:7]), int(value[8:10]),
                   int(value[11:13]), int(value[14:16]), int(value[17:19]))
    tail = value[19:]
    fraction = 0
    if tail.startswith("."):
        i = 1
        while i < len(tail) and "0" <= tail[i] <= "9":
            i += 1
        if i == 1:
            raise ValueError("Ugyldig tidsfraktion")
        fraction = int((tail[1:i] + "000")[:3])
        tail = tail[i:]
    if tail != "Z":
        if len(tail) != 6 or tail[0] not in "+-" or tail[3] != ":":
            raise ValueError("planlagt_tid mangler gyldig tidszone")
        h, m = int(tail[1:3]), int(tail[4:6])
        if not 0 <= h <= 23 or not 0 <= m <= 59:
            raise ValueError("Ugyldig tidszone")
        sec -= (1 if tail[0] == "+" else -1) * (h * 3600 + m * 60)
    return sec * 1000 + fraction


def parse_http_date(value):
    if not isinstance(value, str):
        raise ValueError("API-svaret mangler HTTP Date-header")
    parts = value.split()
    if len(parts) != 6 or parts[-1] != "GMT":
        raise ValueError("Ugyldig HTTP Date-header")
    _, day, month, year, clock, _ = parts
    if int(year) < getattr(config, "MIN_SERVER_YEAR", 2026):
        raise ValueError("Raspberry Pi har ikke en gyldig dato")
    h, m, s = map(int, clock.split(":"))
    return _seconds(int(year), MONTHS.index(month)+1, int(day), h, m, s) * 1000


def _last_sunday(y, m):
    # Marts og oktober har begge 31 dage. 2000-01-01 var loerdag.
    day_index = _seconds(y, m, 31, 0, 0, 0) // 86400
    return 31 - (day_index + 6) % 7


def copenhagen_day(timestamp):
    """Lokal kalenderdag som heltal. EU-regler: skift kl. 01 UTC."""
    y = 2000
    while y < 2099 and timestamp >= _seconds(y + 1, 1, 1, 0, 0, 0) * 1000:
        y += 1
    start = _seconds(y, 3, _last_sunday(y, 3), 1, 0, 0) * 1000
    end = _seconds(y, 10, _last_sunday(y, 10), 1, 0, 0) * 1000
    offset = 7200000 if start <= timestamp < end else 3600000
    return (timestamp + offset) // 86400000


def schedule_init():
    return {"last_time": None, "last_tick": None, "next": None,
            "due": [], "missed": [], "ready": False}


def schedule_poll(state):
    """Tidligere kalenderdage -> FEJL; i dag -> klar/vent.

    Kun planlaegning. Ingen motorhandling eller automatisk dosering.
    """
    state.update({"next": None, "due": [], "missed": [], "ready": False})
    try:
        rows, date = get_udleveringer(with_date=True)
        now = parse_http_date(date)
        tick = ticks_ms()
        if state["last_time"] is not None and now < state["last_time"]:
            raise ValueError("Serverens ur gik baglaens")
        state["last_time"] = now
        state["last_tick"] = tick
        today = copenhagen_day(now)
        # Valider alle planlagte poster foer nogen skrivning.
        planned = [(parse_iso(row["planlagt_tid"]), row) for row in rows
                   if row.get("status_kode") == "planlagt"]
        planned.sort(key=lambda item: item[0])
        ids = set()
        for planned_time, row in planned:
            ident = row["udlevering_id"]
            if type(ident) is not int or ident <= 0 or ident in ids:
                raise ValueError("Ugyldigt/dubleret udlevering_id")
            ids.add(ident)
        for planned_time, row in planned:
            ident = row["udlevering_id"]
            if copenhagen_day(planned_time) < today:
                state["missed"].append(row)
                if getattr(config, "MARK_MISSED_AS_FAILED", False):
                    result = set_udleveringsstatus(ident, FEJL, forventet_tid=row["planlagt_tid"])
                    if result is None:
                        print("API|PLAN_AENDRET|ID=%s" % ident)
                        return None  # hent planen igen foer den kan bruges
                    print("API|FEJL_REGISTRERET|ID=%s|TID=%s" % (ident, row["planlagt_tid"]))
                else:
                    print("API|FORPASSET_TEST|ID=%s|TID=%s" % (ident, row["planlagt_tid"]))
                continue
            if state["next"] is None:
                state["next"] = row
            if planned_time <= now:
                state["due"].append(row)
                print("API|FORFALDEN_I_DAG|ID=%s|AFVENTER_SENSORLOGIK" % ident)
        if len(state["due"]) > 1:
            print("API|FLERE_FORFALDNE_I_DAG|INGEN_AUTOMATISK_UDLEVERING")
        if state["next"] is not None:
            row = state["next"]
            print("API|NAESTE|ID=%s|TID=%s" % (row["udlevering_id"], row["planlagt_tid"]))
        else:
            print("API|INGEN_PLANLAGTE_UDLEVERINGER")
        state["ready"] = True
        return state["next"]
    except Exception as error:
        state.update({"next": None, "due": [], "missed": [], "ready": False})
        print("FEJL|API_TID_ELLER_STATUS|" + str(error))
        return None
