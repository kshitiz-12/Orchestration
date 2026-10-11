"""Live flight offers for travel replies — price, times, stops/layover (not compare links).

Sources (first configured wins):
1. SerpAPI Google Flights — SERPAPI_API_KEY
2. Amadeus Flight Offers — AMADEUS_CLIENT_ID + AMADEUS_CLIENT_SECRET
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_FLIGHT_ASK = re.compile(
    r"\b(?:flights?|air\s*tickets?|airline|fly(?:ing)?|book\s+(?:a\s+)?flight|arrange\s+(?:a\s+)?flight)\b",
    re.I,
)

# Common city / airport → IATA (India-first; Amadeus/SerpAPI can refine further)
_CITY_IATA: dict[str, str] = {
    "DELHI": "DEL",
    "NEW DELHI": "DEL",
    "DEL": "DEL",
    "IGI": "DEL",
    "MUMBAI": "BOM",
    "BOMBAY": "BOM",
    "BOM": "BOM",
    "BANGALORE": "BLR",
    "BENGALURU": "BLR",
    "BLR": "BLR",
    "CHENNAI": "MAA",
    "MADRAS": "MAA",
    "MAA": "MAA",
    "HYDERABAD": "HYD",
    "HYD": "HYD",
    "KOLKATA": "CCU",
    "CALCUTTA": "CCU",
    "CCU": "CCU",
    "PUNE": "PNQ",
    "PNQ": "PNQ",
    "GOA": "GOI",
    "GOI": "GOI",
    "AHMEDABAD": "AMD",
    "AMD": "AMD",
    "KOCHI": "COK",
    "COCHIN": "COK",
    "COK": "COK",
    "JAIPUR": "JAI",
    "JAI": "JAI",
    "LUCKNOW": "LKO",
    "LKO": "LKO",
    "CHANDIGARH": "IXC",
    "IXC": "IXC",
    "RANCHI": "IXR",
    "IXR": "IXR",
    "GURGAON": "DEL",
    "GURUGRAM": "DEL",
    "NOIDA": "DEL",
}

_AIRLINE_NAMES: dict[str, str] = {
    "6E": "IndiGo",
    "AI": "Air India",
    "UK": "Vistara",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "I5": "AirAsia India",
    "IX": "Air India Express",
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "SQ": "Singapore Airlines",
    "LH": "Lufthansa",
    "BA": "British Airways",
}


@dataclass
class FlightOption:
    airline: str
    flight_numbers: str
    depart_at: str  # local display e.g. "20 Oct 06:15"
    arrive_at: str
    duration: str  # e.g. "2h 45m"
    stops: str  # "Non-stop" | "1 stop (BOM, 1h 10m)"
    price: str  # e.g. "INR 4,299"
    origin: str = ""
    destination: str = ""
    cabin: str = "Economy"
    source: str = ""
    summary: str = ""  # one-line for logs / legacy

    def __post_init__(self) -> None:
        if not self.summary:
            self.summary = (
                f"{self.airline} {self.flight_numbers}: {self.depart_at} → {self.arrive_at}, "
                f"{self.duration}, {self.stops}, {self.price}"
            )


def wants_flight(text: str) -> bool:
    return bool(_FLIGHT_ASK.search(text or ""))


def _city(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    text = re.sub(
        r"\b(?:from|to|airport|office|hq|hotel|stay|guest\s*house)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text[:80]


def flight_options_are_usable(options: Any) -> bool:
    """True when stored options have real fare/time fields (not old compare-link stubs)."""
    if not options or not isinstance(options, list):
        return False
    for opt in options:
        if not isinstance(opt, dict):
            continue
        if opt.get("price") and opt.get("depart_at") and opt.get("airline"):
            return True
        # Old link-only shape
        if opt.get("url") or opt.get("source") in {"google_flights", "kayak", "web"}:
            continue
    return False


def resolve_iata(place: str) -> Optional[str]:
    key = _city(place).upper()
    if not key:
        return None
    if key in _CITY_IATA:
        return _CITY_IATA[key]
    if len(key) == 3 and key.isalpha():
        return key
    for name, code in _CITY_IATA.items():
        if name in key or key in name:
            return code
    return None


def parse_travel_date(raw: str, *, today: Optional[date] = None) -> Optional[str]:
    """Best-effort → YYYY-MM-DD for offer APIs."""
    text = (raw or "").strip()
    if not text:
        return None
    today = today or date.today()
    # ISO
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    # 20 Oct / 20 October / 20 Oct 2026
    m = re.search(
        r"\b(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:\s*(20\d{2}))?\b",
        text,
        re.I,
    )
    if m:
        months = {n: i for i, n in enumerate(
            "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1
        )}
        day_n = int(m.group(1))
        month_n = months[m.group(2)[:3].title()]
        year_n = int(m.group(3)) if m.group(3) else today.year
        try:
            d = date(year_n, month_n, day_n)
        except ValueError:
            return None
        if d < today and not m.group(3):
            d = date(year_n + 1, month_n, day_n)
        return d.isoformat()
    # next Monday / Friday
    m = re.search(
        r"\b(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
        re.I,
    )
    if m:
        want = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(
            m.group(1).lower()
        )
        delta = (want - today.weekday()) % 7
        if delta == 0 or "next" in text.lower():
            delta = 7 if delta == 0 else delta
        return (today + timedelta(days=delta)).isoformat()
    return None


def _fmt_iso_local(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M")
    except ValueError:
        return iso[:16]


def _fmt_duration_iso(iso_dur: str) -> str:
    # PT2H45M → 2h 45m
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", (iso_dur or "").upper())
    if not m:
        return iso_dur or ""
    h, mi = m.group(1), m.group(2)
    parts = []
    if h:
        parts.append(f"{int(h)}h")
    if mi:
        parts.append(f"{int(mi)}m")
    return " ".join(parts) or iso_dur


def _fmt_minutes(mins: int) -> str:
    h, m = divmod(max(0, int(mins)), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _money(amount: Any, currency: str = "INR") -> str:
    try:
        n = float(amount)
    except (TypeError, ValueError):
        return f"{currency} {amount}"
    if currency.upper() in {"INR", "RS", "₹"}:
        return f"INR {n:,.0f}"
    return f"{currency} {n:,.2f}"


def _airline_name(code: str, fallback: str = "") -> str:
    code = (code or "").upper()
    return _AIRLINE_NAMES.get(code) or fallback or code


# --- SerpAPI Google Flights -------------------------------------------------

def _serpapi_flights(origin: str, dest: str, day: str, *, max_options: int) -> list[FlightOption]:
    settings = get_settings()
    key = (settings.serpapi_api_key or "").strip()
    if not key:
        return []
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": day,
        "currency": "INR",
        "hl": "en",
        "api_key": key,
        "type": "2",  # one-way
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get("https://serpapi.com/search.json", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("flight_serpapi_failed", error=str(exc)[:200])
        return []

    buckets = []
    for key_name in ("best_flights", "other_flights"):
        buckets.extend(data.get(key_name) or [])
    options: list[FlightOption] = []
    for row in buckets:
        legs = row.get("flights") or []
        if not legs:
            continue
        first, last = legs[0], legs[-1]
        airlines = []
        numbers = []
        for leg in legs:
            airlines.append(leg.get("airline") or _airline_name(leg.get("airline_code") or ""))
            fn = leg.get("flight_number") or ""
            if fn:
                numbers.append(fn if re.search(r"[A-Z]", fn) else f"{leg.get('airline_code', '')}{fn}".strip())
        layovers = row.get("layovers") or []
        if len(legs) <= 1 and not layovers:
            stops = "Non-stop"
        else:
            bits = []
            for lay in layovers:
                name = lay.get("name") or lay.get("id") or "stop"
                dur = lay.get("duration")
                if dur is not None:
                    bits.append(f"{name}, {_fmt_minutes(dur)}")
                else:
                    bits.append(str(name))
            stops = f"{len(legs) - 1} stop" + ("s" if len(legs) > 2 else "")
            if bits:
                stops += f" ({'; '.join(bits)})"
        dep = first.get("departure_airport") or {}
        arr = last.get("arrival_airport") or {}
        dep_t = f"{day[8:10]} {datetime.strptime(day, '%Y-%m-%d').strftime('%b')} {dep.get('time', '')}".strip()
        # SerpAPI often gives time as "6:00 AM" without date
        if dep.get("time") and not re.search(r"\d{1,2}\s+[A-Z][a-z]{2}", dep_t):
            dep_t = f"{datetime.strptime(day, '%Y-%m-%d').strftime('%d %b')} {dep.get('time')}"
        arr_t = arr.get("time") or ""
        if arr_t and not re.search(r"\d{1,2}\s+[A-Z][a-z]{2}", arr_t):
            arr_t = f"{datetime.strptime(day, '%Y-%m-%d').strftime('%d %b')} {arr_t}"
        total_mins = row.get("total_duration")
        duration = _fmt_minutes(total_mins) if total_mins is not None else ""
        price = _money(row.get("price"), "INR") if row.get("price") is not None else "Price on request"
        airline = " / ".join(dict.fromkeys(a for a in airlines if a)) or "Airline"
        options.append(
            FlightOption(
                airline=airline,
                flight_numbers=" + ".join(numbers) or "—",
                depart_at=dep_t or "—",
                arrive_at=arr_t or "—",
                duration=duration or "—",
                stops=stops,
                price=price,
                origin=origin,
                destination=dest,
                source="serpapi",
            )
        )
        if len(options) >= max_options:
            break
    return options


# --- Amadeus ----------------------------------------------------------------

_amadeus_token: dict[str, Any] = {"access_token": "", "expires_at": 0.0}


def _amadeus_token() -> Optional[str]:
    settings = get_settings()
    cid = (settings.amadeus_client_id or "").strip()
    secret = (settings.amadeus_client_secret or "").strip()
    if not cid or not secret:
        return None
    import time

    if _amadeus_token["access_token"] and _amadeus_token["expires_at"] > time.time() + 30:
        return str(_amadeus_token["access_token"])
    base = (settings.amadeus_hostname or "https://test.api.amadeus.com").rstrip("/")
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{base}/v1/security/oauth2/token",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("flight_amadeus_auth_failed", error=str(exc)[:200])
        return None
    _amadeus_token["access_token"] = payload.get("access_token") or ""
    _amadeus_token["expires_at"] = time.time() + float(payload.get("expires_in") or 1800)
    return str(_amadeus_token["access_token"]) or None


def _amadeus_flights(origin: str, dest: str, day: str, *, max_options: int) -> list[FlightOption]:
    token = _amadeus_token()
    if not token:
        return []
    settings = get_settings()
    base = (settings.amadeus_hostname or "https://test.api.amadeus.com").rstrip("/")
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": dest,
        "departureDate": day,
        "adults": 1,
        "currencyCode": "INR",
        "max": max_options,
        "nonStop": "false",
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(
                f"{base}/v2/shopping/flight-offers",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("flight_amadeus_search_failed", error=str(exc)[:200])
        return []

    carriers = (data.get("dictionaries") or {}).get("carriers") or {}
    options: list[FlightOption] = []
    for offer in data.get("data") or []:
        itineraries = offer.get("itineraries") or []
        if not itineraries:
            continue
        segs = itineraries[0].get("segments") or []
        if not segs:
            continue
        first, last = segs[0], segs[-1]
        numbers = []
        airlines = []
        for seg in segs:
            code = seg.get("carrierCode") or ""
            airlines.append(_airline_name(code, carriers.get(code) or code))
            numbers.append(f"{code}{seg.get('number') or ''}")
        if len(segs) == 1:
            stops = "Non-stop"
        else:
            mids = []
            for i in range(len(segs) - 1):
                arr = datetime.fromisoformat(segs[i]["arrival"]["at"])
                dep = datetime.fromisoformat(segs[i + 1]["departure"]["at"])
                wait = int((dep - arr).total_seconds() // 60)
                airport = segs[i]["arrival"].get("iataCode") or ""
                mids.append(f"{airport}, {_fmt_minutes(wait)}")
            stops = f"{len(segs) - 1} stop" + ("s" if len(segs) > 2 else "")
            if mids:
                stops += f" ({'; '.join(mids)})"
        price_obj = offer.get("price") or {}
        options.append(
            FlightOption(
                airline=" / ".join(dict.fromkeys(airlines)) or "Airline",
                flight_numbers=" + ".join(numbers),
                depart_at=_fmt_iso_local(first["departure"]["at"]),
                arrive_at=_fmt_iso_local(last["arrival"]["at"]),
                duration=_fmt_duration_iso(itineraries[0].get("duration") or ""),
                stops=stops,
                price=_money(price_obj.get("grandTotal") or price_obj.get("total"), price_obj.get("currency") or "INR"),
                origin=origin,
                destination=dest,
                cabin=((offer.get("travelerPricings") or [{}])[0].get("fareDetailsBySegment") or [{}])[0].get("cabin")
                or "Economy",
                source="amadeus",
            )
        )
        if len(options) >= max_options:
            break
    return options


def search_flights(
    origin: str,
    destination: str,
    travel_date: str,
    *,
    max_options: int = 5,
) -> list[FlightOption]:
    """Return concrete flight offers (price / times / layover). No booking links."""
    origin_c = _city(origin)
    destination_c = _city(destination)
    if not origin_c or not destination_c:
        return []

    origin_iata = resolve_iata(origin_c)
    dest_iata = resolve_iata(destination_c)
    day = parse_travel_date(travel_date) or parse_travel_date(
        f"{origin_c} {destination_c} {travel_date}"
    )
    if not day:
        day = (date.today() + timedelta(days=7)).isoformat()

    if not origin_iata or not dest_iata:
        logger.warning("flight_iata_unresolved", origin=origin_c, destination=destination_c)
        return []

    options = _serpapi_flights(origin_iata, dest_iata, day, max_options=max_options)
    if not options:
        options = _amadeus_flights(origin_iata, dest_iata, day, max_options=max_options)
    if not options:
        logger.warning(
            "flight_offers_empty",
            origin=origin_iata,
            destination=dest_iata,
            date=day,
            hint="Set SERPAPI_API_KEY or AMADEUS_CLIENT_ID/SECRET for live fares",
        )
    return options[:max_options]


def format_flight_options_for_mail(options: list[FlightOption] | list[dict]) -> str:
    if not options:
        return (
            "I couldn't pull live flight inventories right now (fare feed not configured or no seats found). "
            "Reply with preferred airline / time window and I'll ask Travel Desk to quote exact options."
        )
    lines = [
        "Here are live flight options (reply with the option number you prefer, or say a different date/time):",
        "",
    ]
    for i, opt in enumerate(options, start=1):
        if isinstance(opt, dict):
            airline = opt.get("airline") or ""
            numbers = opt.get("flight_numbers") or ""
            depart = opt.get("depart_at") or ""
            arrive = opt.get("arrive_at") or ""
            duration = opt.get("duration") or ""
            stops = opt.get("stops") or ""
            price = opt.get("price") or opt.get("price_hint") or ""
            cabin = opt.get("cabin") or "Economy"
        else:
            airline, numbers = opt.airline, opt.flight_numbers
            depart, arrive = opt.depart_at, opt.arrive_at
            duration, stops, price = opt.duration, opt.stops, opt.price
            cabin = opt.cabin or "Economy"
        lines.append(f"{i}. {airline} {numbers}".strip())
        lines.append(f"   Depart: {depart}")
        lines.append(f"   Arrive: {arrive}")
        lines.append(f"   Duration: {duration}  |  {stops}")
        lines.append(f"   Fare: {price}  ({cabin})")
        lines.append("")
    lines.append("Once you pick one, I'll send it to the Travel Desk to book (manager approval if required).")
    return "\n".join(lines).rstrip()


def options_as_dicts(options: list[FlightOption]) -> list[dict]:
    return [asdict(o) for o in options]
