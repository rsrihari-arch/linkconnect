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

from app.models import Base, Account, Campaign, Lead, AccountStatus, CampaignStatus, LeadStatus, FollowUpStep, FollowUpLog
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


# --- Human-like Behavior ---

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1280, "height": 800},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]


def get_warmup_limit(campaign_created_at) -> int:
    """Gradually increase daily limit during warmup period to avoid detection."""
    days_active = (datetime.datetime.utcnow() - campaign_created_at).days
    if days_active >= settings.warmup_days:
        return settings.daily_limit_max
    # Ramp up: start at warmup_start_limit, increase by ~3-4 per day
    ramp = settings.warmup_start_limit + int((settings.daily_limit_max - settings.warmup_start_limit) * (days_active / settings.warmup_days))
    return max(settings.warmup_start_limit, min(ramp, settings.daily_limit_max))


async def human_like_scroll(page):
    """Scroll the page like a human would - random distance, random pauses."""
    scrolls = random.randint(1, 3)
    for _ in range(scrolls):
        distance = random.randint(200, 500)
        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def create_stealth_context(pw, cookies: Optional[List[dict]] = None, headless: bool = True):
    """Create a browser context with anti-detection measures."""
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    ua = random.choice(USER_AGENTS)
    vp = random.choice(VIEWPORTS)
    context = await browser.new_context(
        user_agent=ua,
        viewport=vp,
        locale="en-US",
        timezone_id="Asia/Kolkata",
    )
    # Remove navigator.webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)
    if cookies:
        await context.add_cookies(cookies)
    return browser, context


# --- LinkedIn Automation ---

async def login_account(email: str, password: str, account_id: int, db: Session, headless: bool = True) -> List[dict]:
    """Login to LinkedIn. If verification is needed, waits for user to submit code via the platform."""
    from playwright.async_api import async_playwright

    print(f"[Login] Logging into LinkedIn as {email}...")
    pw = await async_playwright().start()
    browser, context = await create_stealth_context(pw, headless=headless)
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
            await page.wait_for_url("**/feed/**", timeout=15000)
        except Exception:
            current_url = page.url
            # Check if verification/challenge page
            if "challenge" in current_url or "checkpoint" in current_url or "verify" in current_url:
                print(f"[Login] Verification required at {current_url}")

                # Mark account as "verifying" so frontend shows code input
                account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
                if account:
                    account.status = AccountStatus.verifying
                    account.login_error = "LinkedIn sent a verification code to your email. Please enter it on the platform."
                    account.verification_code = None
                    db.commit()

                # Look for the code input field on the page
                code_input = page.locator('input[name="pin"], input#input__email_verification_pin, input[name="code"]')

                # Poll the database for up to 3 minutes waiting for the user to submit the code
                print(f"[Login] Waiting for verification code (up to 3 minutes)...")
                code = None
                for _ in range(36):  # 36 * 5 seconds = 3 minutes
                    if shutdown_requested:
                        return []
                    await asyncio.sleep(5)
                    db.expire_all()
                    account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
                    if account and account.verification_code:
                        code = account.verification_code
                        print(f"[Login] Got verification code from user.")
                        break

                if not code:
                    print(f"[Login] Timed out waiting for verification code.")
                    if account:
                        account.login_error = "Verification code timed out. Please try logging in again."
                        account.status = AccountStatus.login_required
                        db.commit()
                    return []

                # Enter the code
                if await code_input.count() > 0:
                    await code_input.first.fill(code)
                    await asyncio.sleep(1)
                    # Submit
                    submit_btn = page.locator('button[type="submit"], button:has-text("Submit"), button:has-text("Verify")')
                    if await submit_btn.count() > 0:
                        await submit_btn.first.click()
                    else:
                        await code_input.first.press("Enter")
                    await asyncio.sleep(5)
                else:
                    print(f"[Login] Could not find code input field on page.")
                    if account:
                        account.login_error = "Could not find verification input on LinkedIn page."
                        account.status = AccountStatus.login_required
                        db.commit()
                    return []

                # Check if we made it to feed
                try:
                    await page.wait_for_url("**/feed/**", timeout=15000)
                except Exception:
                    print(f"[Login] Still not at feed after code entry. URL: {page.url}")
                    if account:
                        account.login_error = f"Verification failed. LinkedIn may need additional steps. Current page: {page.url}"
                        account.status = AccountStatus.login_required
                        account.verification_code = None
                        db.commit()
                    return []

            elif "wrong" in current_url or "error" in current_url:
                print(f"[Login] Login error at {current_url}")
                account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
                if account:
                    account.login_error = "Invalid email or password."
                    account.status = AccountStatus.login_required
                    db.commit()
                return []
            else:
                print(f"[Login] Unexpected page: {current_url}")
                return []

        await asyncio.sleep(3)
        cookies = await context.cookies()
        print(f"[Login] Success! Got {len(cookies)} cookies.")

        # Clear any error and verification state
        account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
        if account:
            account.verification_code = None
            account.login_error = None
            db.commit()

        return [
            {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"]}
            for c in cookies
        ]
    except Exception as e:
        print(f"[Login] Failed: {e}")
        account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
        if account:
            account.login_error = str(e)
            db.commit()
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
    browser, context = await create_stealth_context(pw, cookies=cookies, headless=headless)
    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 7))
        await human_like_scroll(page)
        await asyncio.sleep(random.uniform(1, 3))

        # Get the topcard section (contains name, headline, action buttons)
        top_card = page.locator('section[componentkey*="Topcard"]')
        if await top_card.count() == 0:
            # Fallback: first section inside main
            top_card = page.locator('main section').first

        # Check connection status from topcard text
        top_text = await top_card.text_content() or ""
        if "Pending" in top_text:
            return {"status": "already_invited"}
        if "· 1st" in top_text:
            return {"status": "already_connected"}

        # Strategy 1: Connect link/button in topcard (LinkedIn uses <a> tags for Connect)
        connect_btn = None
        connect_link = top_card.locator('a[href*="/preload/custom-invite/"]')
        if await connect_link.count() > 0:
            connect_btn = connect_link.first

        # Strategy 1b: Connect as a <button> inside the topcard
        if not connect_btn:
            connect_btn = await _find_connect_button_in(top_card)

        # Strategy 2: aria-label selectors on page (match person's name)
        if not connect_btn:
            name_el = top_card.locator('h1')
            person_name = ""
            if await name_el.count() > 0:
                person_name = (await name_el.first.text_content() or "").strip()

            if person_name:
                for sel in [f'button[aria-label*="Invite {person_name}"]', f'a[aria-label*="Invite {person_name}"]']:
                    btn = page.locator(sel)
                    if await btn.count() > 0:
                        connect_btn = btn.first
                        break

        # Strategy 3: "More" dropdown in topcard
        if not connect_btn:
            more_btn = top_card.locator('button[aria-label="More"]')
            if await more_btn.count() > 0:
                await more_btn.first.click()
                await asyncio.sleep(1.5)
                # Look for Connect in the dropdown menu
                menu_items = page.locator('[role="menu"] [role="menuitem"]')
                count = await menu_items.count()
                for i in range(count):
                    item_text = (await menu_items.nth(i).text_content() or "").strip()
                    if item_text.lower().startswith("connect"):
                        await menu_items.nth(i).click()
                        await asyncio.sleep(2)
                        # This click may open a modal or send directly
                        # Check for send button
                        for send_sel in ['button[aria-label="Send invitation"]', 'button[aria-label="Send now"]', 'button:has-text("Send")']:
                            send_btn = page.locator(send_sel)
                            if await send_btn.count() > 0:
                                await send_btn.first.click()
                                await asyncio.sleep(2)
                                return {"status": "sent"}
                        return {"status": "sent"}  # Connect from menu often sends directly

        if not connect_btn:
            return {"status": "no_connect_button"}

        await connect_btn.click()
        await asyncio.sleep(3)

        # LinkedIn may navigate to /preload/custom-invite/ page or show a modal
        # Handle the invitation page/modal
        if message:
            # Try to find and fill message/note field
            note_field = page.locator('textarea[name="message"], textarea#custom-message, textarea.connect-button-send-invite__custom-message, textarea')
            if await note_field.count() > 0:
                first_textarea = note_field.first
                if await first_textarea.is_visible():
                    await first_textarea.fill(message[:300])
                    await asyncio.sleep(1)
            else:
                # Try "Add a note" button first
                add_note_btn = page.locator('button:has-text("Add a note")')
                if await add_note_btn.count() > 0:
                    await add_note_btn.click()
                    await asyncio.sleep(1)
                    note_field = page.locator('textarea')
                    if await note_field.count() > 0:
                        await note_field.first.fill(message[:300])
                        await asyncio.sleep(1)

        # Click Send (try multiple selectors)
        for send_selector in [
            'button[aria-label="Send invitation"]',
            'button[aria-label="Send now"]',
            'button:has-text("Send")',
        ]:
            send_btn = page.locator(send_selector)
            if await send_btn.count() > 0:
                await send_btn.first.click()
                await asyncio.sleep(2)
                return {"status": "sent"}

        # Try "Send without a note"
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


async def _find_connect_button_in(container):
    """Find a Connect button within a specific container (e.g. topcard section)."""
    btn = container.locator('button:has-text("Connect")')
    count = await btn.count()
    for i in range(count):
        text = (await btn.nth(i).text_content() or "").strip()
        if text.lower() == "connect":
            return btn.nth(i)
    return None


async def send_linkedin_message(
    cookies: List[dict],
    profile_url: str,
    message: str,
    headless: bool = True,
) -> dict:
    """Send a LinkedIn message to someone you're connected with."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser, context = await create_stealth_context(pw, cookies=cookies, headless=headless)
    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 7))
        await human_like_scroll(page)
        await asyncio.sleep(random.uniform(1, 3))

        # Find Message button in topcard
        top_card = page.locator('section[componentkey*="Topcard"]')
        if await top_card.count() == 0:
            top_card = page.locator('main section').first

        msg_btn = None
        # Try link first (LinkedIn uses <a> tags)
        msg_link = top_card.locator('a:has-text("Message")')
        if await msg_link.count() > 0:
            msg_btn = msg_link.first
        else:
            # Try button
            msg_button = top_card.locator('button:has-text("Message")')
            if await msg_button.count() > 0:
                msg_btn = msg_button.first

        if not msg_btn:
            return {"status": "no_message_button"}

        await msg_btn.click()
        await asyncio.sleep(3)

        # Find the message input in the messaging overlay/panel
        msg_input = page.locator('div[role="textbox"][contenteditable="true"]')
        if await msg_input.count() == 0:
            # Try textarea fallback
            msg_input = page.locator('textarea[name="message"]')
        if await msg_input.count() == 0:
            return {"status": "no_message_input"}

        await msg_input.first.click()
        await asyncio.sleep(0.5)
        await msg_input.first.fill(message)
        await asyncio.sleep(1)

        # Click Send
        send_btn = page.locator('button[type="submit"]:has-text("Send"), button.msg-form__send-button, button[aria-label="Send"]')
        if await send_btn.count() > 0:
            await send_btn.first.click()
            await asyncio.sleep(2)
            return {"status": "sent"}

        # Fallback: press Enter
        await msg_input.first.press("Enter")
        await asyncio.sleep(2)
        return {"status": "sent"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


async def check_connection_accepted(
    cookies: List[dict],
    profile_url: str,
    headless: bool = True,
) -> bool:
    """Check if a previously invited person has accepted the connection."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser, context = await create_stealth_context(pw, cookies=cookies, headless=headless)
    page = await context.new_page()

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 5))

        top_card = page.locator('section[componentkey*="Topcard"]')
        if await top_card.count() == 0:
            top_card = page.locator('main section').first

        top_text = await top_card.text_content() or ""
        return "· 1st" in top_text
    except Exception:
        return False
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


def _render_template(template: str, lead) -> str:
    """Replace template variables like {first_name}, {name}, {company}."""
    text = template
    name = lead.name or ""
    parts = name.split() if name else []
    text = text.replace("{first_name}", parts[0] if parts else "")
    text = text.replace("{last_name}", parts[-1] if len(parts) > 1 else "")
    text = text.replace("{name}", name)
    text = text.replace("{linkedin_url}", lead.linkedin_url or "")
    return text


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
        try:
            cookies = asyncio.run(login_account(account.email, password, account.id, db, headless=headless))
        except Exception as e:
            print(f"[Login] Account {account.email} login error: {e}")
            account.login_error = str(e)
            db.commit()
            continue

        if cookies:
            account.session_cookies = json.dumps(cookies)
            account.status = AccountStatus.active
            account.login_error = None
            account.verification_code = None
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

        # Apply warm-up: gradually increase limit for new campaigns
        warmup_limit = get_warmup_limit(campaign.created_at)
        effective_limit = min(campaign.daily_limit, warmup_limit)
        remaining = effective_limit - sent_today
        if remaining <= 0:
            print(f"[Campaign] Daily limit reached ({sent_today}/{effective_limit}). Skipping.")
            continue

        days_active = (datetime.datetime.utcnow() - campaign.created_at).days
        warmup_note = f" (warmup: day {days_active}/{settings.warmup_days})" if days_active < settings.warmup_days else ""
        print(f"[Campaign] {sent_today}/{effective_limit} sent today. {remaining} remaining.{warmup_note}")

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
            elif status == "already_invited":
                lead.status = LeadStatus.invited
                print(f"  [Lead] --> Already invited (pending).")
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


def process_connection_checks(db: Session, headless: bool):
    """Check if invited leads have accepted the connection."""
    # Find leads that were invited more than 1 day ago (give time for acceptance)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    campaigns = db.execute(
        select(Campaign).where(Campaign.status.in_([CampaignStatus.active, CampaignStatus.completed]))
    ).scalars().all()

    for campaign in campaigns:
        if shutdown_requested:
            break

        # Only check campaigns that have follow-up steps
        steps = db.execute(
            select(FollowUpStep).where(FollowUpStep.campaign_id == campaign.id)
        ).scalars().all()
        if not steps:
            continue

        account = db.execute(
            select(Account).where(Account.id == campaign.account_id)
        ).scalar_one_or_none()
        if not account or not account.session_cookies:
            continue

        cookies = json.loads(account.session_cookies)

        # Find invited leads to check
        invited_leads = db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign.id,
                Lead.status == LeadStatus.invited,
                Lead.last_action_at <= cutoff,
            ).limit(10)
        ).scalars().all()

        if not invited_leads:
            continue

        print(f"\n[Connection Check] Campaign: {campaign.name} - checking {len(invited_leads)} invited leads")

        for lead in invited_leads:
            if shutdown_requested:
                break

            accepted = asyncio.run(check_connection_accepted(
                cookies=cookies,
                profile_url=lead.linkedin_url,
                headless=headless,
            ))

            if accepted:
                lead.status = LeadStatus.connected
                lead.connected_at = datetime.datetime.utcnow()
                print(f"  [Check] {lead.name or 'Unknown'} --> Connected!")
            else:
                # Update last_action_at so we don't check too frequently
                lead.last_action_at = datetime.datetime.utcnow()

            db.commit()
            await_delay = random.uniform(3, 8)
            for _ in range(int(await_delay)):
                if shutdown_requested:
                    break
                asyncio.run(asyncio.sleep(1))


def process_followups(db: Session, headless: bool):
    """Send follow-up messages to connected leads."""
    campaigns = db.execute(
        select(Campaign).where(Campaign.status.in_([CampaignStatus.active, CampaignStatus.completed]))
    ).scalars().all()

    for campaign in campaigns:
        if shutdown_requested:
            break

        steps = db.execute(
            select(FollowUpStep)
            .where(FollowUpStep.campaign_id == campaign.id)
            .order_by(FollowUpStep.step_order)
        ).scalars().all()

        if not steps:
            continue

        account = db.execute(
            select(Account).where(Account.id == campaign.account_id)
        ).scalar_one_or_none()
        if not account or not account.session_cookies:
            continue

        cookies = json.loads(account.session_cookies)

        # Find connected leads
        connected_leads = db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign.id,
                Lead.status == LeadStatus.connected,
                Lead.connected_at.isnot(None),
            )
        ).scalars().all()

        if not connected_leads:
            continue

        print(f"\n[Follow-up] Campaign: {campaign.name} - {len(connected_leads)} connected leads")

        for lead in connected_leads:
            if shutdown_requested:
                break

            for step in steps:
                if shutdown_requested:
                    break

                # Check if this step was already sent
                already_sent = db.execute(
                    select(FollowUpLog).where(
                        FollowUpLog.lead_id == lead.id,
                        FollowUpLog.step_id == step.id,
                    )
                ).scalar_one_or_none()

                if already_sent:
                    continue

                # Check if enough days have passed since connection
                days_since = (datetime.datetime.utcnow() - lead.connected_at).days
                if days_since < step.delay_days:
                    break  # Steps are ordered, so if this one isn't due, later ones won't be either

                # Render message with template variables
                message = _render_template(step.message_template, lead)

                print(f"  [Follow-up] {lead.name or 'Unknown'} - Step {step.step_order} (day {step.delay_days})")

                result = asyncio.run(send_linkedin_message(
                    cookies=cookies,
                    profile_url=lead.linkedin_url,
                    message=message,
                    headless=headless,
                ))

                log = FollowUpLog(
                    lead_id=lead.id,
                    step_id=step.id,
                    status=result.get("status", "failed"),
                    error_message=result.get("error"),
                )
                db.add(log)
                db.commit()

                if result.get("status") == "sent":
                    print(f"  [Follow-up] --> Message sent!")
                else:
                    print(f"  [Follow-up] --> Failed: {result.get('status')}")

                # Delay between messages
                delay = random.uniform(settings.min_delay, settings.max_delay)
                print(f"  [Delay] Waiting {delay:.0f}s...")
                for _ in range(int(delay)):
                    if shutdown_requested:
                        break
                    asyncio.run(asyncio.sleep(1))

                break  # Only send one step per lead per cycle


def run_once(headless: bool = True):
    """Run one cycle: process logins, campaigns, connection checks, follow-ups."""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print(f"[Worker] Starting cycle at {datetime.datetime.utcnow().isoformat()}")
        print("=" * 60)

        process_logins(db, headless)
        process_campaigns(db, headless)
        process_connection_checks(db, headless)
        process_followups(db, headless)

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
