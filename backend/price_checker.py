import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from db import get_db, get_blocked_retailers
from notifier import send_discord, send_email

log = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}



# ── PricesAPI.io ──────────────────────────────────────────────────────────────

def fetch_pricesapi(query: str, api_key: str, blocked: set) -> list[dict]:
    if not api_key:
        return []

    headers = {"x-api-key": api_key}
    base = "https://api.pricesapi.io/api/v1"

    # Step 1 — search for products matching the query
    try:
        resp = requests.get(
            f"{base}/products/search",
            headers=headers,
            params={"q": query, "limit": 5},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"PricesAPI search error for '{query}': {e}")
        return []

    products = data.get("data", {}).get("results", [])
    if not products:
        log.info(f"    PricesAPI: no products found for '{query}'")
        return []

    # Step 2 — fetch offers for the best matching product
    product_id = products[0].get("id")
    if not product_id:
        return []

    try:
        resp = requests.get(
            f"{base}/products/{product_id}/offers",
            headers=headers,
            params={"country": "us"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"PricesAPI offers error for product {product_id}: {e}")
        return []

    results = []
    offers = data.get("data", {}).get("offers", data.get("data", []))
    if isinstance(offers, dict):
        offers = offers.get("results", [])

    for item in offers:
        try:
            price_raw = (
                item.get("price")
                or item.get("current_price")
                or item.get("salePrice")
            )
            if price_raw is None:
                continue
            price = float(str(price_raw).replace("$", "").replace(",", "").strip())
            retailer = (
                item.get("store")
                or item.get("merchant")
                or item.get("retailer")
                or item.get("seller")
                or "Unknown"
            )
            url   = item.get("url") or item.get("link") or item.get("productUrl") or ""
            title = item.get("title") or item.get("name") or query

            if price > 0 and retailer.lower().strip() not in blocked:
                results.append({
                    "retailer": retailer,
                    "price": price,
                    "url": url,
                    "title": title,
                    "source": "pricesapi",
                })
        except (ValueError, TypeError):
            continue

    log.info(f"    PricesAPI: {len(results)} offer(s) for '{query}'")
    return results


# ── SlickDeals RSS ────────────────────────────────────────────────────────────

def fetch_slickdeals(query: str, blocked: set) -> list[dict]:
    url = (
        "https://slickdeals.net/newsearch.php"
        f"?q={query.replace(' ', '+')}"
        "&mode=frontpage&searcharea=deals&rss=1"
    )
    results = []
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        root    = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item"):
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            match = re.search(r'\$\s*([\d,]+\.?\d{0,2})', title)
            if not match:
                continue
            try:
                price = float(match.group(1).replace(",", ""))
            except ValueError:
                continue

            if any(b in title.lower() for b in blocked):
                continue

            if price > 0:
                results.append({
                    "retailer": "SlickDeals",
                    "price": price,
                    "url": link,
                    "title": title,
                    "source": "slickdeals",
                })
    except ET.ParseError as e:
        log.warning(f"SlickDeals parse error: {e}")
    except Exception as e:
        log.warning(f"SlickDeals error: {e}")

    log.info(f"    SlickDeals: {len(results)} deal(s)")
    return results


# ── Combined ──────────────────────────────────────────────────────────────────

def get_prices(query: str, api_key: str = "", use_slickdeals: bool = True) -> list[dict]:
    """Fetch from all enabled sources, deduplicated by (retailer, price)."""
    blocked = get_blocked_retailers()
    results = []
    if api_key:
        results.extend(fetch_pricesapi(query, api_key, blocked))
    if use_slickdeals:
        results.extend(fetch_slickdeals(query, blocked))

    seen, deduped = set(), []
    for r in results:
        key = (r["retailer"].lower(), r["price"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


# ── Quota helper ──────────────────────────────────────────────────────────────

def recommended_interval_minutes(part_count: int, monthly_limit: int = 1000) -> int:
    if part_count == 0:
        return 120
    safe_calls        = int(monthly_limit * 0.8)
    calls_per_day     = safe_calls / 30
    minutes_per_check = (24 * 60) / (calls_per_day / part_count)
    for snap in [30, 60, 120, 180, 240, 360, 720]:
        if snap >= minutes_per_check:
            return snap
    return 720


# ── Main scheduled job ────────────────────────────────────────────────────────

def check_all_parts():
    log.info("── Starting price check ──")

    with get_db() as db:
        parts    = db.execute("SELECT * FROM parts").fetchall()
        settings = db.execute("SELECT * FROM settings WHERE id=1").fetchone()

    if not parts:
        log.info("No parts configured, skipping")
        return

    settings        = dict(settings) if settings else {}
    api_key         = settings.get("pricesapi_key", "")
    use_slickdeals  = bool(settings.get("slickdeals_enabled", 1))
    discord_webhook = settings.get("discord_webhook", "")
    email_cfg = {
        "from":      settings.get("email_from", ""),
        "to":        settings.get("email_to", ""),
        "password":  settings.get("email_password", ""),
        "smtp_host": settings.get("email_smtp_host", "smtp.gmail.com"),
        "smtp_port": settings.get("email_smtp_port", 587),
    }

    if not api_key and not use_slickdeals:
        log.warning("No price sources configured")
        return

    deals_found = []

    for part in [dict(p) for p in parts]:
        log.info(f"  [{part['name']}] target ${part['target_price']:.2f}")
        prices = get_prices(part["search_query"], api_key, use_slickdeals)
        time.sleep(2)

        if not prices:
            log.info(f"    No prices found")
            continue

        with get_db() as db:
            for p in prices:
                db.execute(
                    "INSERT INTO price_history (part_id, retailer, price, url) VALUES (?,?,?,?)",
                    (part["id"], p["retailer"], p["price"], p.get("url", ""))
                )

        for p in prices:
            log.info(f"    {p['retailer']:20s}  ${p['price']:.2f}  [{p['source']}]")
            if p["price"] < part["target_price"]:
                with get_db() as db:
                    state = db.execute(
                        "SELECT last_alerted_price FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    ).fetchone()

                if state and state["last_alerted_price"] == p["price"]:
                    log.info(f"    → Already alerted, skipping")
                    continue

                log.info(f"    *** DEAL: {p['retailer']} @ ${p['price']:.2f} ***")
                deals_found.append({**p, "part": part})

                if discord_webhook:
                    send_discord(discord_webhook, part["name"], p["retailer"],
                                 p["price"], part["target_price"], p.get("url"))
                send_email(email_cfg, part["name"], p["retailer"],
                           p["price"], part["target_price"], p.get("url"))

                with get_db() as db:
                    db.execute(
                        """INSERT INTO alert_state (part_id, retailer, last_alerted_price)
                           VALUES (?,?,?) ON CONFLICT(part_id, retailer)
                           DO UPDATE SET last_alerted_price=excluded.last_alerted_price""",
                        (part["id"], p["retailer"], p["price"])
                    )
            else:
                with get_db() as db:
                    db.execute(
                        "DELETE FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    )

    log.info(f"── Done. {len(deals_found)} new deal(s) ──\n")

    if len(deals_found) >= 2 and discord_webhook:
        lines = [f"• **{d['part']['name']}** @ ${d['price']:.2f} on {d['retailer']}" for d in deals_found]
        send_discord(discord_webhook, "Multiple deals found!",
                     "\n".join(lines), None, None, None, is_summary=True)
