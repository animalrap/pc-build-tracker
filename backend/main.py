import os
import sqlite3
import logging
import threading
import schedule
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from price_checker import check_all_parts, get_prices
from notifier import send_discord, send_email
from db import init_db, get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="PC Build Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ── Models ────────────────────────────────────────────────────────────────────
class Part(BaseModel):
    name: str
    category: str
    search_query: str
    target_price: float
    notes: Optional[str] = ""


class PartUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    search_query: Optional[str] = None
    target_price: Optional[float] = None
    notes: Optional[str] = None


class Settings(BaseModel):
    discord_webhook: Optional[str] = ""
    email_from: Optional[str] = ""
    email_to: Optional[str] = ""
    email_password: Optional[str] = ""
    email_smtp_host: Optional[str] = "smtp.gmail.com"
    email_smtp_port: Optional[int] = 587
    check_interval_minutes: Optional[int] = 120
    total_budget: Optional[float] = 0
    pricesapi_key: Optional[str] = ""
    slickdeals_enabled: Optional[int] = 1


# ── Parts CRUD ────────────────────────────────────────────────────────────────
@app.get("/api/parts")
def list_parts():
    with get_db() as db:
        rows = db.execute("SELECT * FROM parts ORDER BY category, name").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/parts")
def add_part(part: Part):
    with get_db() as db:
        db.execute(
            "INSERT INTO parts (name, category, search_query, target_price, notes) VALUES (?,?,?,?,?)",
            (part.name, part.category, part.search_query, part.target_price, part.notes)
        )
    return {"ok": True}


@app.put("/api/parts/{part_id}")
def update_part(part_id: int, part: PartUpdate):
    with get_db() as db:
        existing = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Part not found")
        updates = {k: v for k, v in part.dict().items() if v is not None}
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            db.execute(f"UPDATE parts SET {sets} WHERE id=?", (*updates.values(), part_id))
    return {"ok": True}


@app.delete("/api/parts/{part_id}")
def delete_part(part_id: int):
    with get_db() as db:
        db.execute("DELETE FROM parts WHERE id=?", (part_id,))
        db.execute("DELETE FROM price_history WHERE part_id=?", (part_id,))
    return {"ok": True}


# ── Price history ─────────────────────────────────────────────────────────────
@app.get("/api/parts/{part_id}/history")
def price_history(part_id: int, days: int = 30):
    with get_db() as db:
        rows = db.execute(
            """SELECT retailer, price, url, checked_at FROM price_history
               WHERE part_id=? AND checked_at >= datetime('now', ?)
               ORDER BY checked_at DESC""",
            (part_id, f"-{days} days")
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/parts/{part_id}/best-price")
def best_price(part_id: int):
    with get_db() as db:
        row = db.execute(
            """SELECT retailer, price, url, checked_at FROM price_history
               WHERE part_id=? ORDER BY price ASC LIMIT 1""",
            (part_id,)
        ).fetchone()
        return dict(row) if row else {}


# ── Manual price check ────────────────────────────────────────────────────────
@app.post("/api/check")
def trigger_check():
    threading.Thread(target=check_all_parts, daemon=True).start()
    return {"ok": True, "message": "Price check started"}


@app.get("/api/prices/{part_id}")
def fetch_prices_now(part_id: int, query: Optional[str] = None):
    """
    If query param is provided, use it directly (for live "Test" button).
    Otherwise look up the part's search_query from the DB.
    part_id=0 is a sentinel value meaning "ad-hoc query, no part".
    """
    with get_db() as db:
        settings = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    settings = dict(settings) if settings else {}
    api_key = settings.get("pricesapi_key", "")
    use_slickdeals = bool(settings.get("slickdeals_enabled", 1))

    if query:
        return get_prices(query, api_key, use_slickdeals)

    with get_db() as db:
        part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return get_prices(dict(part)["search_query"], api_key, use_slickdeals)


# ── Build summary ─────────────────────────────────────────────────────────────
@app.get("/api/summary")
def build_summary():
    with get_db() as db:
        parts = db.execute("SELECT * FROM parts").fetchall()
        total_target = 0
        total_best = 0
        categories = {}
        for p in parts:
            p = dict(p)
            total_target += p["target_price"]
            best = db.execute(
                "SELECT price FROM price_history WHERE part_id=? ORDER BY price ASC LIMIT 1",
                (p["id"],)
            ).fetchone()
            best_price = best["price"] if best else None
            total_best += best_price if best_price else p["target_price"]
            cat = p["category"]
            categories[cat] = categories.get(cat, 0) + 1

        settings = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
        budget = dict(settings)["total_budget"] if settings else 0

        return {
            "part_count": len(parts),
            "total_target": round(total_target, 2),
            "total_best_prices": round(total_best, 2),
            "budget": budget,
            "budget_remaining": round(budget - total_best, 2) if budget else None,
            "categories": categories,
        }


# ── Settings ──────────────────────────────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    with get_db() as db:
        row = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if not row:
            return {}
        d = dict(row)
        # Never expose secrets — return boolean presence flags instead
        d["has_email_password"] = bool(d.pop("email_password", ""))
        d["has_pricesapi_key"]  = bool(d.pop("pricesapi_key", ""))
        return d


@app.post("/api/settings")
def save_settings(s: Settings):
    with get_db() as db:
        existing = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if existing:
            existing = dict(existing)
            # Preserve existing secrets if the submitted value is blank
            email_password = s.email_password if s.email_password else existing.get("email_password", "")
            pricesapi_key  = s.pricesapi_key  if s.pricesapi_key  else existing.get("pricesapi_key", "")
            db.execute(
                """UPDATE settings SET discord_webhook=?, email_from=?, email_to=?,
                   email_password=?, email_smtp_host=?, email_smtp_port=?,
                   check_interval_minutes=?, total_budget=?,
                   pricesapi_key=?, slickdeals_enabled=? WHERE id=1""",
                (s.discord_webhook, s.email_from, s.email_to, email_password,
                 s.email_smtp_host, s.email_smtp_port, s.check_interval_minutes,
                 s.total_budget, pricesapi_key, s.slickdeals_enabled)
            )
        else:
            db.execute(
                """INSERT INTO settings (id, discord_webhook, email_from, email_to,
                   email_password, email_smtp_host, email_smtp_port,
                   check_interval_minutes, total_budget, pricesapi_key, slickdeals_enabled)
                   VALUES (1,?,?,?,?,?,?,?,?,?,?)""",
                (s.discord_webhook, s.email_from, s.email_to, s.email_password,
                 s.email_smtp_host, s.email_smtp_port, s.check_interval_minutes,
                 s.total_budget, s.pricesapi_key, s.slickdeals_enabled)
            )
    restart_scheduler()
    return {"ok": True}


@app.get("/api/quota")
def quota_advice():
    """Return recommended check interval based on part count and API limits."""
    from price_checker import recommended_interval_minutes
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) as n FROM parts").fetchone()["n"]
    recommended = recommended_interval_minutes(count)
    calls_per_month = int((60 / recommended) * 24 * 30 * count)
    return {
        "part_count": count,
        "recommended_interval_minutes": recommended,
        "estimated_calls_per_month": calls_per_month,
        "monthly_limit": 1000,
        "headroom_percent": round((1 - calls_per_month / 1000) * 100, 1),
    }


@app.post("/api/settings/test-discord")
def test_discord():
    with get_db() as db:
        row = db.execute("SELECT discord_webhook FROM settings WHERE id=1").fetchone()
        if not row or not row["discord_webhook"]:
            raise HTTPException(status_code=400, detail="No webhook configured")
        send_discord(row["discord_webhook"], "Test", "PC Build Tracker test notification!", None, None)
    return {"ok": True}


# ── Scheduler ─────────────────────────────────────────────────────────────────
_scheduler_thread = None

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(30)

def restart_scheduler():
    global _scheduler_thread
    schedule.clear()
    with get_db() as db:
        row = db.execute("SELECT check_interval_minutes FROM settings WHERE id=1").fetchone()
        interval = dict(row)["check_interval_minutes"] if row else 60
    schedule.every(interval).minutes.do(check_all_parts)
    log.info(f"Scheduler set: every {interval} minutes")

def start_scheduler():
    global _scheduler_thread
    restart_scheduler()
    _scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    _scheduler_thread.start()
    log.info("Scheduler started")

@app.on_event("startup")
def startup():
    start_scheduler()
    log.info("PC Build Tracker started")
