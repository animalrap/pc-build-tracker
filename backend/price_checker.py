import re
import os
import time
import logging
import requests
import xml.etree.ElementTree as ET
from db import get_db
from notifier import send_discord, send_email

log = logging.getLogger(__name__)

PRICES_API_BASE = "https://api.pricesapi.io/v1"
SLICKDEALS_RSS = "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&rss=1&q="
KNOWN_RETAILERS = ["Newegg", "Amazon", "Best Buy", "Micro Center", "B&H", "Adorama", "Walmart", "Antonline"]


def get_pricesapi_key() -> str:
    try:
        with get_db() as db:
            row = db.execute("SELECT pricesapi_key FROM settings WHERE id=1").fetchone()
            if row and row["pricesapi_key"]:
                return row["pricesapi_key"]
    except Exception:
        pass
    return os.getenv("PRICES_API_KEY", "")


def _parse_price(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(re.sub(r"[^\d.]", "", str(raw)))
    except ValueError:
        return None


def fetch_pricesapi_prices(query: str) -> list[dict]:
    api_key = get_pricesapi_key()
    if not api_key:
        log.warning("    PricesAPI key not configured — skipping")
        return []

    results = []
    try:
        resp = requests.get(
            f"{PRICES_API_BASE}/search",
            headers={"X-API-Key": api_key},
            params={"q": query, "country": "us"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("products", []))

        seen = set()
        for item in items:
            try:
                offers = item.get("offers", item.get("sellers", []))
                if offers:
                    for offer in offers:
                        price = _parse_price(offer.get("price") or offer.get("current_price"))
                        retailer = offer.get("retailer") or offer.get("store") or offer.get("merchant", "Unknown")
                        url = offer.get("url") or offer.get("link", item.get("url", ""))
                        if price and (retailer, price) not in seen:
                            seen.add((retailer, price))
                            results.append({"retailer": retailer, "price": price, "url": url, "title": query})
                else:
                    price = _parse_price(item.get("price") or item.get("current_price"))
                    retailer = item.get("retailer") or item.get("store") or item.get("merchant", "Unknown")
                    url = item.get("url") or item.get("link", "")
                    if price and (retailer, price) not in seen:
                        seen.add((retailer, price))
                        results.append({"retailer": retailer, "price": price, "url": url, "title": query})
            except Exception as e:
                log.debug(f"Skipping malformed item: {e}")
                continue

        log.info(f"    PricesAPI: {len(results)} result(s)")
    except requests.HTTPError as e:
        log.warning(f"    PricesAPI HTTP error: {e} — {resp.text[:200]}")
    except Exception as e:
        log.warning(f"    PricesAPI error: {e}")

    return results


def fetch_slickdeals(query: str) -> list[dict]:
    results = []
    try:
        url = SLICKDEALS_RSS + requests.utils.quote(query)
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []

        price_pattern = re.compile(r'\$\s*([\d,]+\.?\d{2})')
        for item in channel.findall("item")[:10]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")
            price_match = price_pattern.search(title) or price_pattern.search(description)
            if not price_match:
                continue
            try:
                price = float(price_match.group(1).replace(",", ""))
                if price < 10:
                    continue
                retailer = "Unknown"
                for store in KNOWN_RETAILERS:
                    if store.lower() in title.lower() or store.lower() in description.lower():
                        retailer = store
                        break
                results.append({"retailer": f"{retailer} (SlickDeals)", "price": price, "url": link, "title": title})
            except ValueError:
                continue

        log.info(f"    SlickDeals: {len(results)} deal(s)")
    except Exception as e:
        log.warning(f"    SlickDeals error: {e}")

    return results


def get_shopping_prices(query: str) -> list[dict]:
    results = []
    results.extend(fetch_pricesapi_prices(query))
    results.extend(fetch_slickdeals(query))

    seen = set()
    deduped = []
    for r in results:
        key = (r["retailer"].lower(), r["price"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def check_all_parts():
    log.info("── Starting price check for all parts ──")

    with get_db() as db:
        parts = db.execute("SELECT * FROM parts").fetchall()
        settings = db.execute("SELECT * FROM settings WHERE id=1").fetchone()

    if not parts:
        log.info("No parts configured, skipping check")
        return

    settings = dict(settings) if settings else {}
    discord_webhook = settings.get("discord_webhook", "")
    email_cfg = {
        "from": settings.get("email_from", ""),
        "to": settings.get("email_to", ""),
        "password": settings.get("email_password", ""),
        "smtp_host": settings.get("email_smtp_host", "smtp.gmail.com"),
        "smtp_port": settings.get("email_smtp_port", 587),
    }

    deals_found = []

    for part in parts:
        part = dict(part)
        log.info(f"  Checking: {part['name']} (target: ${part['target_price']:.2f})")
        prices = get_shopping_prices(part["search_query"])
        time.sleep(2)

        if not prices:
            log.info(f"    No prices found for {part['name']}")
            continue

        with get_db() as db:
            for p in prices:
                db.execute(
                    "INSERT INTO price_history (part_id, retailer, price, url) VALUES (?,?,?,?)",
                    (part["id"], p["retailer"], p["price"], p.get("url", ""))
                )

        for p in prices:
            if p["price"] < part["target_price"]:
                with get_db() as db:
                    state = db.execute(
                        "SELECT last_alerted_price FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    ).fetchone()
                already_alerted = state and state["last_alerted_price"] == p["price"]

                if not already_alerted:
                    log.info(f"    *** DEAL: {p['retailer']} @ ${p['price']:.2f} ***")
                    deals_found.append({**p, "part": part})
                    if discord_webhook:
                        send_discord(discord_webhook, part["name"], p["retailer"], p["price"], part["target_price"], p.get("url"))
                    send_email(email_cfg, part["name"], p["retailer"], p["price"], part["target_price"], p.get("url"))
                    with get_db() as db:
                        db.execute(
                            """INSERT INTO alert_state (part_id, retailer, last_alerted_price)
                               VALUES (?,?,?) ON CONFLICT(part_id, retailer)
                               DO UPDATE SET last_alerted_price=excluded.last_alerted_price""",
                            (part["id"], p["retailer"], p["price"])
                        )
                else:
                    log.info(f"    Already alerted {p['retailer']} @ ${p['price']:.2f}, skipping")
            else:
                with get_db() as db:
                    db.execute(
                        "DELETE FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    )

    log.info(f"── Check complete. {len(deals_found)} new deal(s) found ──\n")

    if len(deals_found) >= 2 and discord_webhook:
        summary_lines = [f"• **{d['part']['name']}** @ ${d['price']:.2f} on {d['retailer']}" for d in deals_found]
        send_discord(discord_webhook, "Multiple deals found!", "\n".join(summary_lines), None, None, None, is_summary=True)
