import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from db import get_db
from notifier import send_discord, send_email

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def get_shopping_prices(query: str) -> list[dict]:
    """
    Fetch prices via Google Shopping RSS feed.
    Returns list of {retailer, price, url, title} dicts.
    """
    url = "https://www.google.com/search"
    params = {
        "q": query,
        "tbm": "shop",
        "tbs": "vw:l",   # list view
        "num": "20",
        "hl": "en",
        "gl": "us",
    }

    results = []
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # Extract price + merchant pairs from Google Shopping HTML
        # Pattern: look for structured data or visible price blocks
        price_pattern = re.compile(r'\$\s*([\d,]+\.?\d*)')
        merchant_pattern = re.compile(
            r'"(Newegg|Best Buy|Micro Center|B&H|Amazon|Walmart|Antonline|adorama|Fry\'s|Costco|Target)[^"]*"',
            re.IGNORECASE
        )

        # Try to parse Google Shopping JSON-LD structured data
        import json
        json_pattern = re.compile(r'AF_initDataCallback\(({.*?})\)', re.DOTALL)

        # Simpler approach: use Google Shopping RSS
        rss_results = fetch_google_rss(query)
        if rss_results:
            return rss_results

        # Fallback: regex scrape
        prices = price_pattern.findall(html)
        merchants = merchant_pattern.findall(html)

        seen = set()
        for i, (merchant, price_str) in enumerate(zip(merchants, prices)):
            try:
                price = float(price_str.replace(",", ""))
                key = (merchant.lower(), price)
                if key not in seen and price > 10:
                    seen.add(key)
                    results.append({
                        "retailer": merchant.title(),
                        "price": price,
                        "url": f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop",
                        "title": query,
                    })
            except ValueError:
                continue

    except Exception as e:
        log.warning(f"Google Shopping fetch error for '{query}': {e}")

    return results


def fetch_google_rss(query: str) -> list[dict]:
    """Use Google Shopping RSS feed — most reliable public endpoint."""
    url = "https://www.google.com/shopping/product/1/specs"
    rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"

    # Google Product Search RSS (public, no auth)
    shopping_rss = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&output=rss"

    results = []
    try:
        resp = requests.get(shopping_rss, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        # Try to parse as RSS
        try:
            root = ET.fromstring(resp.content)
            ns = {"g": "http://base.google.com/ns/1.0"}
            channel = root.find("channel")
            if channel is None:
                return []
            for item in channel.findall("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                price_el = item.find("g:price", ns)
                merchant_el = item.find("g:store", ns)
                if price_el is not None:
                    try:
                        price = float(re.sub(r"[^\d.]", "", price_el.text))
                        merchant = merchant_el.text if merchant_el is not None else "Unknown"
                        results.append({
                            "retailer": merchant,
                            "price": price,
                            "url": link,
                            "title": title,
                        })
                    except (ValueError, TypeError):
                        continue
        except ET.ParseError:
            pass

    except Exception as e:
        log.warning(f"RSS fetch error: {e}")

    # If RSS gave nothing, fall back to SerpApi-style price extraction from HTML
    if not results:
        results = scrape_prices_from_html(query)

    return results


def scrape_prices_from_html(query: str) -> list[dict]:
    """
    Robust HTML price extraction from Google Shopping results.
    Targets known retailer names and adjacent price patterns.
    """
    results = []
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop&num=20&hl=en&gl=us"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        html = resp.text

        # Known retailers to look for
        retailers = [
            "Newegg", "Best Buy", "Micro Center", "Amazon",
            "B&H Photo", "Walmart", "Antonline", "Adorama",
        ]

        seen = set()
        for retailer in retailers:
            if retailer.lower() in html.lower():
                # Find price near retailer name
                idx = html.lower().find(retailer.lower())
                snippet = html[max(0, idx-200):idx+500]
                prices = re.findall(r'\$\s*([\d,]+\.?\d{2})', snippet)
                for p in prices:
                    try:
                        price = float(p.replace(",", ""))
                        if 50 < price < 2000:  # sanity check
                            key = (retailer, price)
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    "retailer": retailer,
                                    "price": price,
                                    "url": url,
                                    "title": query,
                                })
                            break
                    except ValueError:
                        continue

    except Exception as e:
        log.warning(f"HTML scrape error: {e}")

    return results


def check_all_parts():
    """Main scheduled job — check prices for all parts and send alerts."""
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
        time.sleep(3)  # polite delay between parts

        if not prices:
            log.info(f"    No prices found for {part['name']}")
            continue

        # Save all prices to history
        with get_db() as db:
            for p in prices:
                db.execute(
                    "INSERT INTO price_history (part_id, retailer, price, url) VALUES (?,?,?,?)",
                    (part["id"], p["retailer"], p["price"], p.get("url", ""))
                )

        # Check for deals
        for p in prices:
            if p["price"] < part["target_price"]:
                # Check alert state — don't re-alert same price
                with get_db() as db:
                    state = db.execute(
                        "SELECT last_alerted_price FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    ).fetchone()

                already_alerted = state and state["last_alerted_price"] == p["price"]

                if not already_alerted:
                    log.info(f"    *** DEAL: {p['retailer']} @ ${p['price']:.2f} (target ${part['target_price']:.2f}) ***")
                    deals_found.append({**p, "part": part})

                    # Send notifications
                    if discord_webhook:
                        send_discord(discord_webhook, part["name"], p["retailer"], p["price"], part["target_price"], p.get("url"))
                    send_email(email_cfg, part["name"], p["retailer"], p["price"], part["target_price"], p.get("url"))

                    # Update alert state
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
                # Price above target — clear alert state so we re-alert on next drop
                with get_db() as db:
                    db.execute(
                        "DELETE FROM alert_state WHERE part_id=? AND retailer=?",
                        (part["id"], p["retailer"])
                    )

    log.info(f"── Check complete. {len(deals_found)} new deal(s) found ──\n")

    # Send a build summary alert if multiple deals found
    if len(deals_found) >= 2 and discord_webhook:
        summary_lines = [f"• **{d['part']['name']}** @ ${d['price']:.2f} on {d['retailer']}" for d in deals_found]
        send_discord(
            discord_webhook,
            "Multiple deals found!",
            "\n".join(summary_lines),
            None, None, None,
            is_summary=True
        )
