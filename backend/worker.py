#!/usr/bin/env python3
"""
LinkConnect Automation Worker

Standalone script that:
1. Logs into LinkedIn accounts (saves session cookies)
2. Processes active campaigns (sends connection requests)
3. Respects daily limits and adds random delays

Run: python worker.py
Env: DATABASE_URL, ENCRYPTION_KEY (same as backend)

Can be run as a cron job, systemd service, or manually.
"""

import asyncio
import json
import os
import random
import ssl
import sys
import datetime
import signal
from typing import Optional, List

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, Session

# Add parent to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Base, Account, Campaign, Lead, AccountStatus, CampaignStatus, LeadStatus
from app.config import settings


# --- Database Setup ---

def get_engine():
    db_url = os.environ.get("DATABASE_URL", settings.database_url)
    connect_args = {}

    if "postgresql://" in db_url and "+" not in db_url.split("://")[0]:
        db_url = db_url.replace("postgresql://", "postgresql+pg8000://")

    if "sslmode=" in db_url:
        db_url = db_url.split("?")[0]
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl_context"] = ssl_context

    return create_engine(db_url, echo=False, pool_pre_ping=True, connect_args=connect_args)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

# Graceful shutdown
shutdown_requested = False

def handle_shutdown(signum, frame):
    global shutdown_requested
    print("\n[Worker] Shutdown requested, finishing current task...")
    shutdown_requested = True

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# --- LinkedIn Automation ---

async def login_account(email: str, password: str, headless: bool = True) -> List[dict]:
    """Login to LinkedIn and return session cookies."""
    from playwright.async_api import async_playwright

    print(f"[Login] Logging into LinkedIn as {email}...")
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()

    try:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("#username", timeout=15000)
        await page.fill("#username", email)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.fill("#password", password)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.click('button[type="submit"]')

        # Wait for redirect to feed
        try:
            await page.wait_for_url("**/feed/**", timeout=30000)
        except Exception:
            # Check if there's a security challenge
            current_url = page.url
            if "challenge" in current_url or "checkpoint" in current_url:
                print(f"[Login] Security challenge detected at {current_url}")
                if not headless:
                    print("[Login] Please complete the challenge in the browser window...")
                    print("[Login] Waiting up to 2 minutes for you to solve it...")
                    await page.wait_for_url("**/feed/**", timeout=120000)
                else:
                    print("[Login] Re-run with HEADLESS=false to handle the challenge.")
                    return []

        await asyncio.sleep(3)
        cookies = await context.cookies()
        print(f"[Login] Success! Got {len(cookies)} cookies.")
        return [
            {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]}
            for c in cookies
        ]
    except Exception as e:
        print(f"[Login] Failed: {e}")
        return []
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


async def send_connection_request(
    cookies: List[dict],
    profile_url: str,
    message: Optional[str] = None,
    headless: bool = True,
) -> dict:
    """Visit a LinkedIn profile and send a connection request."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    await context.add_cookies(cookies)
    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(2, 5))

        # Check if already connected
        page_text = await page.text_content("body") or ""
        if "Message" in page_text and "Following" in page_text:
            return {"status": "already_connected"}

        # Find the Connect button
        connect_btn = await _find_connect_button(page)

        if not connect_btn:
            # Try the "More" dropdown
            more_btn = page.locator('button:has-text("More")')
            if await more_btn.count() > 0:
                await more_btn.first.click()
                await asyncio.sleep(1)
                connect_btn = await _find_connect_button(page)

        if not connect_btn:
            return {"status": "no_connect_button"}

        await connect_btn.click()
        await asyncio.sleep(2)

        # Add a note if message template is provided
        if message:
            add_note_btn = page.locator('button:has-text("Add a note")')
            if await add_note_btn.count() > 0:
                await add_note_btn.click()
                await asyncio.sleep(1)

                note_field = page.locator('textarea[name="message"]')
                if await note_field.count() == 0:
                    note_field = page.locator("#custom-message")
                if await note_field.count() > 0:
                    await note_field.fill(message[:300])
                    await asyncio.sleep(1)

        # Click Send
        send_btn = page.locator('button:has-text("Send")')
        if await send_btn.count() > 0:
            await send_btn.first.click()
            await asyncio.sleep(2)
            return {"status": "sent"}

        send_now_btn = page.locator('button:has-text("Send without a note")')
        if await send_now_btn.count() > 0:
            await send_now_btn.click()
            await asyncio.sleep(2)
            return {"status": "sent"}

        return {"status": "send_failed"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


async def _find_connect_button(page):
    selectors = [
        'button:has-text("Connect")',
        'button[aria-label*="connect" i]',
        'button[aria-label*="Connect" i]',
    ]
    for selector in selectors:
        btn = page.locator(selector)
        count = await btn.count()
        for i in range(count):
            text = await btn.nth(i).text_content()
            if text and "connect" in text.lower().strip() and "connected" not in text.lower():
                return btn.nth(i)
    return None


# --- Worker Logic ---

def process_logins(db: Session, headless: bool):
    """Login to all accounts that need it."""
    accounts = db.execute(
        select(Account).where(Account.status == AccountStatus.login_required)
    ).scalars().all()

    for account in accounts:
        if shutdown_requested:
            break

        password = settings.decrypt(account.encrypted_password)
        cookies = asyncio.run(login_account(account.email, password, headless=headless))

        if cookies:
            account.session_cookies = json.dumps(cookies)
            account.status = AccountStatus.active
            print(f"[Login] Account {account.email} is now active.")
        else:
            print(f"[Login] Account {account.email} login failed.")

        db.commit()


def process_campaigns(db: Session, headless: bool):
    """Process all active campaigns."""
    campaigns = db.execute(
        select(Campaign).where(Campaign.status == CampaignStatus.active)
    ).scalars().all()

    if not campaigns:
        print("[Worker] No active campaigns.")
        return

    for campaign in campaigns:
        if shutdown_requested:
            break

        print(f"\n[Campaign] Processing: {campaign.name} (ID: {campaign.id})")

        # Get the account
        account = db.execute(
            select(Account).where(Account.id == campaign.account_id)
        ).scalar_one_or_none()

        if not account or account.status != AccountStatus.active or not account.session_cookies:
            print(f"[Campaign] Skipping - account not active or no session.")
            continue

        cookies = json.loads(account.session_cookies)

        # Check daily limit
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = db.execute(
            select(func.count(Lead.id)).where(
                Lead.campaign_id == campaign.id,
                Lead.status.in_([LeadStatus.invited, LeadStatus.connected]),
                Lead.last_action_at >= today_start,
            )
        ).scalar() or 0

        remaining = campaign.daily_limit - sent_today
        if remaining <= 0:
            print(f"[Campaign] Daily limit reached ({campaign.daily_limit}). Skipping.")
            continue

        print(f"[Campaign] {sent_today}/{campaign.daily_limit} sent today. {remaining} remaining.")

        # Get pending leads
        leads = db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign.id,
                (Lead.status == LeadStatus.pending)
                | ((Lead.status == LeadStatus.failed) & (Lead.retry_count < 1)),
            ).limit(remaining)
        ).scalars().all()

        if not leads:
            # Check if campaign is complete
            pending_count = db.execute(
                select(func.count(Lead.id)).where(
                    Lead.campaign_id == campaign.id,
                    Lead.status == LeadStatus.pending,
                )
            ).scalar() or 0

            if pending_count == 0:
                campaign.status = CampaignStatus.completed
                db.commit()
                print(f"[Campaign] All leads processed. Campaign completed.")
            else:
                print(f"[Campaign] No leads to process right now.")
            continue

        for lead in leads:
            if shutdown_requested:
                break

            print(f"  [Lead] {lead.name or 'Unknown'} - {lead.linkedin_url}")

            result = asyncio.run(send_connection_request(
                cookies=cookies,
                profile_url=lead.linkedin_url,
                message=campaign.message_template,
                headless=headless,
            ))

            status = result.get("status")
            lead.last_action_at = datetime.datetime.utcnow()

            if status == "sent":
                lead.status = LeadStatus.invited
                print(f"  [Lead] --> Invited!")
            elif status == "already_connected":
                lead.status = LeadStatus.connected
                print(f"  [Lead] --> Already connected.")
            elif status in ("no_connect_button", "send_failed"):
                if lead.retry_count >= 1:
                    lead.status = LeadStatus.skipped
                    print(f"  [Lead] --> Skipped (no connect button).")
                else:
                    lead.status = LeadStatus.failed
                    lead.retry_count += 1
                    print(f"  [Lead] --> Failed, will retry.")
            elif status == "error":
                lead.error_message = result.get("error", "Unknown error")
                lead.retry_count += 1
                if lead.retry_count >= 1:
                    lead.status = LeadStatus.failed
                print(f"  [Lead] --> Error: {lead.error_message}")
            else:
                lead.status = LeadStatus.failed
                lead.retry_count += 1

            db.commit()

            # Random delay between actions (20-60 seconds)
            delay = random.uniform(settings.min_delay, settings.max_delay)
            print(f"  [Delay] Waiting {delay:.0f}s...")
            for _ in range(int(delay)):
                if shutdown_requested:
                    break
                asyncio.run(asyncio.sleep(1))


def run_once(headless: bool = True):
    """Run one cycle: process logins then campaigns."""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print(f"[Worker] Starting cycle at {datetime.datetime.utcnow().isoformat()}")
        print("=" * 60)

        process_logins(db, headless)
        process_campaigns(db, headless)

        print(f"\n[Worker] Cycle complete.")
    finally:
        db.close()


def run_loop(interval_minutes: int = 5, headless: bool = True):
    """Run continuously with a delay between cycles."""
    print(f"[Worker] Starting continuous mode (interval: {interval_minutes}m)")
    print(f"[Worker] Headless: {headless}")
    print("[Worker] Press Ctrl+C to stop.\n")

    while not shutdown_requested:
        run_once(headless)

        if shutdown_requested:
            break

        print(f"\n[Worker] Sleeping {interval_minutes} minutes...")
        for _ in range(interval_minutes * 60):
            if shutdown_requested:
                break
            import time
            time.sleep(1)

    print("[Worker] Shut down gracefully.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LinkConnect Automation Worker")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--interval", type=int, default=5, help="Minutes between cycles (default: 5)")
    parser.add_argument("--visible", action="store_true", help="Show browser window (not headless)")
    parser.add_argument("--login-only", action="store_true", help="Only process account logins")
    args = parser.parse_args()

    headless = not args.visible

    # Install playwright browsers if needed
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[Worker] Installing Playwright browsers...")
        os.system("playwright install chromium")

    if args.login_only:
        db = SessionLocal()
        try:
            process_logins(db, headless)
        finally:
            db.close()
    elif args.once:
        run_once(headless)
    else:
        run_loop(args.interval, headless)
