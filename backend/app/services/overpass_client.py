"""
backend/app/services/overpass_client.py
─────────────────────────────────────────
Robust Overpass API client for the RetailIQ agent pipeline.

Ported from backend/pipeline/overpass_client.py (main branch).
- Exponential backoff on 429 / 503 / 504
- Tries 3 mirror URLs before giving up
- Returns raw elements list or [] (never raises)
"""

import logging
import time
import requests

log = logging.getLogger(__name__)

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def query(ql: str, timeout_s: int = 60, retries: int = 3) -> list[dict]:
    """
    Send an Overpass QL query. Returns list of elements or [].
    Tries each mirror up to `retries` times with exponential backoff.
    """
    for mirror in MIRRORS:
        for attempt in range(1, retries + 1):
            try:
                log.info(f"  Overpass {mirror.split('/')[2]} — attempt {attempt}")
                r = requests.post(
                    mirror,
                    data=ql,
                    timeout=timeout_s,
                    headers={"Accept-Charset": "utf-8", "User-Agent": "RetailIQ/2.0"},
                )
                if r.status_code == 200:
                    return r.json().get("elements", [])
                if r.status_code in (429, 503, 504):
                    wait = 2 ** attempt
                    log.warning(f"  HTTP {r.status_code} — waiting {wait}s")
                    time.sleep(wait)
                else:
                    log.error(f"  HTTP {r.status_code} — skipping mirror")
                    break
            except requests.exceptions.Timeout:
                wait = 2 ** attempt
                log.warning(f"  Timeout — waiting {wait}s")
                time.sleep(wait)
            except Exception as e:
                log.error(f"  Error querying {mirror}: {e}")
                break

    log.error("  All Overpass mirrors failed — returning empty list")
    return []
