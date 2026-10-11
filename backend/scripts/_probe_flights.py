"""Probe SerpAPI BLR→IXR fares (prints prices only, never the API key)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main() -> None:
    _load_dotenv()
    key = (os.environ.get("SERPAPI_API_KEY") or "").strip()
    print("serpapi_configured", bool(key), "len", len(key))
    if not key:
        return
    day = "2026-10-14"
    params = {
        "engine": "google_flights",
        "departure_id": "BLR",
        "arrival_id": "IXR",
        "outbound_date": day,
        "currency": "INR",
        "hl": "en",
        "gl": "in",
        "api_key": key,
        "type": "2",
        "travel_class": "1",
        "adults": "1",
        "bags": "1",
        "deep_search": "true",
        "no_cache": "true",
        "sort_by": "1",
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        print("status", r.status_code)
        data = r.json()
        if data.get("error"):
            print("error", data.get("error"))
            return
        insights = data.get("price_insights") or {}
        print("price_insights", insights)
        rows = (data.get("best_flights") or []) + (data.get("other_flights") or [])
        print("rows", len(rows))
        for i, row in enumerate(rows[:8], 1):
            legs = row.get("flights") or []
            nums = [((x.get("flight_number") or "") + "/" + (x.get("airline") or "")) for x in legs]
            print(
                i,
                "list_price=",
                row.get("price"),
                "type=",
                row.get("type"),
                "dur=",
                row.get("total_duration"),
                "legs=",
                len(legs),
                "flights=",
                nums,
                "ext=",
                row.get("extensions"),
                "has_booking_token=",
                bool(row.get("booking_token")),
            )
            token = row.get("booking_token")
            if token and i <= 3:
                b = client.get(
                    "https://serpapi.com/search.json",
                    params={"engine": "google_flights", "booking_token": token, "api_key": key},
                )
                bd = b.json()
                print("  booking_status", b.status_code, "keys", list(bd.keys())[:12])
                opts = bd.get("booking_options") or []
                print("  booking_options", len(opts))
                for j, opt in enumerate(opts[:5], 1):
                    print("   ", j, {k: opt.get(k) for k in list(opt.keys())[:12]})
                    together = opt.get("together") or []
                    for t in together[:3]:
                        print("      together", {k: t.get(k) for k in ("book_with", "price", "local_prices", "airline", "option_title") if k in t or True})
                        print("      together_keys", list(t.keys())[:20])


if __name__ == "__main__":
    main()
