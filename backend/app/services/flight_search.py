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
    fare_note: str = ""  # e.g. bags / basic fare disclaimer
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

_IN_AIRPORTS = set(_CITY_IATA.values())  # domestic India codes we know


def _collect_prices(node: Any, out: list[float]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k in {"price", "total_price", "fare"} and v is not None:
                try:
                    out.append(float(v))
                except (TypeError, ValueError):
                    pass
            else:
                _collect_prices(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_prices(item, out)


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def _serpapi_booking_prices(client: httpx.Client, key: str, booking_token: str) -> list[float]:
    """Bookable agent/airline totals for one itinerary (not the teaser card price)."""
    if not booking_token:
        return []
    try:
        resp = client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_flights",
                "booking_token": booking_token,
                "api_key": key,
                "currency": "INR",
                "gl": "in",
                "hl": "en",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("flight_serpapi_booking_failed", error=str(exc)[:160])
        return []
    prices: list[float] = []
    _collect_prices(data.get("booking_options") or data, prices)
    # Ignore junk / placeholder zeros
    return sorted({p for p in prices if p and p >= 500})


def _pick_realistic_fare(
    *,
    list_price: Optional[float],
    booking_prices: list[float],
    typical_low: Optional[float],
    typical_high: Optional[float],
    domestic_in: bool,
) -> tuple[Optional[float], str]:
    """Prefer real bookable totals; drop teaser list fares far below market."""
    floor = None
    if typical_low:
        floor = float(typical_low) * 0.9
    elif domestic_in:
        # Near-term India domestic one-way teaser cards often show ~5–6k while
        # bookable IndiGo/Air India is 12k+. Don't surface those teasers as the fare.
        floor = 10000.0

    if booking_prices:
        usable = [p for p in booking_prices if floor is None or p >= floor]
        if not usable:
            usable = booking_prices
        # Upper-half median ≈ what airline/OTA checkouts show (not the cheapest bait).
        usable = sorted(usable)
        upper = usable[len(usable) // 2 :]
        fare = _median(upper)
        note = "bookable total (Google Flights India checkout)"
        if list_price is not None and float(list_price) + 1 < fare * 0.85:
            note += f"; card listed {_money(list_price, 'INR')} (basic/teaser — ignored)"
        return fare, note

    if list_price is None:
        return None, ""
    lp = float(list_price)
    if floor is not None and lp < floor:
        # No bookable confirmation and card is below market — skip this row
        return None, "below_market_teaser"
    note = "listed on Google Flights (IN)"
    if typical_high and lp < float(typical_high):
        note += f"; typical up to {_money(typical_high, 'INR')}"
    return lp, note


def _serpapi_flights(origin: str, dest: str, day: str, *, max_options: int) -> list[FlightOption]:
    settings = get_settings()
    key = (settings.serpapi_api_key or "").strip()
    if not key:
        return []
    domestic = origin in _IN_AIRPORTS and dest in _IN_AIRPORTS
    # Match google.co.in/travel/flights (deep_search + gl=in). no_cache avoids stale cheap cards.
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": day,
        "currency": "INR",
        "hl": "en",
        "gl": "in",
        "api_key": key,
        "type": "2",  # one-way
        "travel_class": "1",
        "adults": "1",
        "deep_search": "true",
        "show_hidden": "true",
        "sort_by": "1",
        "no_cache": "true",
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get("https://serpapi.com/search.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                logger.warning("flight_serpapi_error", error=str(data.get("error"))[:200])
                return []

            insights = data.get("price_insights") or {}
            typ = insights.get("typical_price_range") or []
            typical_low = float(typ[0]) if len(typ) >= 1 and typ[0] is not None else None
            typical_high = float(typ[1]) if len(typ) >= 2 and typ[1] is not None else None
            if typical_low is None and insights.get("lowest_price") is not None:
                # lowest alone is often the teaser; bump floor if insights look inflated elsewhere
                try:
                    typical_low = float(insights["lowest_price"])
                except (TypeError, ValueError):
                    typical_low = None

            buckets: list[dict] = []
            for key_name in ("best_flights", "other_flights"):
                buckets.extend(data.get(key_name) or [])
            # Non-stop first for short domestic hops (BLR–IXR etc.)
            buckets.sort(key=lambda r: (len(r.get("flights") or []) > 1, r.get("price") or 0))

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
                    fn = (leg.get("flight_number") or "").strip()
                    if fn:
                        numbers.append(
                            fn if re.search(r"[A-Z]", fn) else f"{leg.get('airline_code', '')}{fn}".strip()
                        )
                layovers = row.get("layovers") or []
                if len(legs) <= 1 and not layovers:
                    stops = "Non-stop"
                else:
                    bits = []
                    for lay in layovers:
                        name = lay.get("name") or lay.get("id") or "stop"
                        dur = lay.get("duration")
                        bits.append(f"{name}, {_fmt_minutes(dur)}" if dur is not None else str(name))
                    stops = f"{len(legs) - 1} stop" + ("s" if len(legs) > 2 else "")
                    if bits:
                        stops += f" ({'; '.join(bits)})"
                dep = first.get("departure_airport") or {}
                arr = last.get("arrival_airport") or {}

                def _when(airport: dict) -> str:
                    raw = (airport.get("time") or "").strip()
                    if re.match(r"20\d{2}-\d{2}-\d{2}", raw):
                        return _fmt_iso_local(raw.replace(" ", "T", 1) if "T" not in raw else raw)
                    if raw:
                        return f"{datetime.strptime(day, '%Y-%m-%d').strftime('%d %b')} {raw}"
                    return "—"

                list_price = row.get("price")
                try:
                    list_f = float(list_price) if list_price is not None else None
                except (TypeError, ValueError):
                    list_f = None

                booking_prices = _serpapi_booking_prices(client, key, row.get("booking_token") or "")
                fare, fare_note = _pick_realistic_fare(
                    list_price=list_f,
                    booking_prices=booking_prices,
                    typical_low=typical_low,
                    typical_high=typical_high,
                    domestic_in=domestic,
                )
                if fare is None:
                    logger.info(
                        "flight_skip_teaser",
                        list_price=list_f,
                        booking=booking_prices[:5],
                        typical_low=typical_low,
                    )
                    continue

                total_mins = row.get("total_duration")
                airline = " / ".join(dict.fromkeys(a for a in airlines if a)) or "Airline"
                cabin = (first.get("travel_class") or "Economy").title()
                fare_note = f"{fare_note}; searched {day} {origin}→{dest} one-way"
                exts = [str(x) for x in (row.get("extensions") or []) if x]
                if exts:
                    fare_note += "; " + "; ".join(exts[:2])

                options.append(
                    FlightOption(
                        airline=airline,
                        flight_numbers=" + ".join(numbers) or "—",
                        depart_at=_when(dep),
                        arrive_at=_when(arr),
                        duration=_fmt_minutes(total_mins) if total_mins is not None else "—",
                        stops=stops,
                        price=_money(fare, "INR"),
                        origin=origin,
                        destination=dest,
                        cabin=cabin,
                        source="serpapi",
                        fare_note=fare_note,
                    )
                )
                if len(options) >= max_options:
                    break

            if options and (typical_low or typical_high):
                tip = "Market check: "
                if typical_low and typical_high:
                    tip += f"typical {_money(typical_low, 'INR')} – {_money(typical_high, 'INR')}"
                elif typical_low:
                    tip += f"from about {_money(typical_low, 'INR')}"
                options[0].fare_note = (options[0].fare_note + " | " if options[0].fare_note else "") + tip

            logger.info(
                "flight_serpapi_ok",
                origin=origin,
                dest=dest,
                day=day,
                options=len(options),
                typical_low=typical_low,
                typical_high=typical_high,
            )
            return options
    except Exception as exc:  # noqa: BLE001
        logger.warning("flight_serpapi_failed", error=str(exc)[:200])
        return []


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
    # Sandbox fares are fictional (often ~5–6k) — never show them as live quotes.
    if "test.api.amadeus.com" in base:
        logger.warning("flight_amadeus_test_skipped", hint="test.api.amadeus.com fares are not real market prices")
        return []
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
        "Here are live one-way flight options from Google Flights (India).",
        "Fares are adult economy; checked bags / seats can add cost on airline sites (so OTA totals may look higher).",
        "Reply with the option number you prefer, or say a different date/time / round-trip:",
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
            fare_note = opt.get("fare_note") or ""
        else:
            airline, numbers = opt.airline, opt.flight_numbers
            depart, arrive = opt.depart_at, opt.arrive_at
            duration, stops, price = opt.duration, opt.stops, opt.price
            cabin = opt.cabin or "Economy"
            fare_note = opt.fare_note or ""
        lines.append(f"{i}. {airline} {numbers}".strip())
        lines.append(f"   Depart: {depart}")
        lines.append(f"   Arrive: {arrive}")
        lines.append(f"   Duration: {duration}  |  {stops}")
        lines.append(f"   Fare: {price}  ({cabin})")
        if fare_note:
            lines.append(f"   Note: {fare_note}")
        lines.append("")
    lines.append("Once you pick one, I'll send it to the Travel Desk to book (manager approval if required).")
    return "\n".join(lines).rstrip()


def options_as_dicts(options: list[FlightOption]) -> list[dict]:
    return [asdict(o) for o in options]
