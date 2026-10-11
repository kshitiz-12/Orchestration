"""Look up flight options from the public web for travel replies over Gmail."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_FLIGHT_ASK = re.compile(
    r"\b(?:flights?|air\s*tickets?|airline|fly(?:ing)?|book\s+(?:a\s+)?flight|arrange\s+(?:a\s+)?flight)\b",
    re.I,
)


@dataclass
class FlightOption:
    summary: str
    url: str
    source: str
    price_hint: Optional[str] = None
    airline: Optional[str] = None


def wants_flight(text: str) -> bool:
    return bool(_FLIGHT_ASK.search(text or ""))


def _city(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    text = re.sub(r"\b(?:from|to|airport|office|hq)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text[:80]


def google_flights_url(origin: str, destination: str, date: str) -> str:
    q = quote_plus(f"Flights to {destination} from {origin} on {date}")
    return f"https://www.google.com/travel/flights?q={q}"


def kayak_url(origin: str, destination: str, date: str) -> str:
    # Kayak accepts free-text search URLs; cities as typed by the employee.
    path = quote_plus(f"{origin}-{destination}/{date}")
    return f"https://www.kayak.com/flights/{path}"


def _duckduckgo_snippets(query: str, *, limit: int = 6) -> list[str]:
    url = "https://html.duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            resp = client.post(
                url,
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; WorkplaceDesk/1.0)"},
            )
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — network is best-effort for mail replies
        logger.warning("flight_search_web_failed", error=str(exc)[:200])
        return []
    # Result snippets sit in result__snippet / result__a
    titles = re.findall(
        r'class="result__a"[^>]*>(.*?)</a>',
        resp.text,
        flags=re.I | re.S,
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
        resp.text,
        flags=re.I | re.S,
    )
    cleaned: list[str] = []
    for raw in titles + snippets:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 20:
            continue
        if not re.search(r"\b(?:flight|airline|airways|₹|INR|Rs\.?|\$|€|depart|nonstop|one[\s-]?way)\b", text, re.I):
            continue
        cleaned.append(text[:220])
        if len(cleaned) >= limit:
            break
    return cleaned


def search_flights(
    origin: str,
    destination: str,
    date: str,
    *,
    max_options: int = 5,
) -> list[FlightOption]:
    """Return flight options for the employee mail: web snippets + live compare links."""
    origin_c = _city(origin)
    destination_c = _city(destination)
    day = (date or "").strip()
    if not origin_c or not destination_c:
        return []

    options: list[FlightOption] = []
    query = f"flights from {origin_c} to {destination_c}" + (f" on {day}" if day else "")
    for i, snippet in enumerate(_duckduckgo_snippets(query), start=1):
        price = None
        m = re.search(r"(?:₹|INR|Rs\.?\s*)([\d,]+)|(?:\$|USD\s*)([\d,]+)", snippet, re.I)
        if m:
            price = m.group(0)
        airline = None
        am = re.search(
            r"\b(IndiGo|Air India|Vistara|SpiceJet|Akasa|Emirates|Qatar|Singapore Airlines|Lufthansa|British Airways)\b",
            snippet,
            re.I,
        )
        if am:
            airline = am.group(1)
        options.append(
            FlightOption(
                summary=snippet,
                url=google_flights_url(origin_c, destination_c, day or "anytime"),
                source="web",
                price_hint=price,
                airline=airline,
            )
        )
        if len(options) >= max_options - 2:
            break

    # Always include live compare links so the employee can pick even if snippets are thin.
    options.append(
        FlightOption(
            summary=f"Compare live fares: {origin_c} → {destination_c}"
            + (f" on {day}" if day else ""),
            url=google_flights_url(origin_c, destination_c, day or "anytime"),
            source="google_flights",
        )
    )
    options.append(
        FlightOption(
            summary=f"Alternate compare (Kayak): {origin_c} → {destination_c}",
            url=kayak_url(origin_c, destination_c, day or ""),
            source="kayak",
        )
    )
    return options[:max_options]


def format_flight_options_for_mail(options: list[FlightOption] | list[dict]) -> str:
    if not options:
        return ""
    lines = ["Flight options I found (reply with the option number you prefer, or say if you want a different time/class):", ""]
    for i, opt in enumerate(options, start=1):
        if isinstance(opt, dict):
            summary = opt.get("summary") or ""
            url = opt.get("url") or ""
            price = opt.get("price_hint")
            airline = opt.get("airline")
        else:
            summary = opt.summary
            url = opt.url
            price = opt.price_hint
            airline = opt.airline
        head = f"{i}. "
        if airline:
            head += f"{airline} — "
        if price:
            head += f"{price} — "
        head += summary
        lines.append(head)
        if url:
            lines.append(f"   {url}")
    lines.append("")
    lines.append("Once you pick one, I'll send it to the Travel Desk to book (manager approval if required).")
    return "\n".join(lines)


def options_as_dicts(options: list[FlightOption]) -> list[dict]:
    return [
        {
            "summary": o.summary,
            "url": o.url,
            "source": o.source,
            "price_hint": o.price_hint,
            "airline": o.airline,
        }
        for o in options
    ]
