import asyncio
import json
import random
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func

from app.database import async_session
from app.models import Campaign, Lead, Account, CampaignStatus, LeadStatus, AccountStatus
from app.config import settings
from app.services.linkedin_automation import LinkedInAutomation

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", minutes=2, id="process_campaigns")
async def process_active_campaigns():
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.active)
        )
        campaigns = result.scalars().all()

        for campaign in campaigns:
            try:
                await _process_campaign(campaign.id)
            except Exception as e:
                print(f"Error processing campaign {campaign.id}: {e}")


async def _process_campaign(campaign_id: int):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign or campaign.status != CampaignStatus.active:
            return

        # Get the linked account
        acct_result = await db.execute(select(Account).where(Account.id == campaign.account_id))
        account = acct_result.scalar_one_or_none()
        if not account or not account.session_cookies or account.status != AccountStatus.active:
            return

        # Check how many requests sent today
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.campaign_id == campaign_id,
                Lead.status.in_([LeadStatus.invited, LeadStatus.connected]),
                Lead.last_action_at >= today_start,
            )
        )
        count_today = sent_today.scalar() or 0

        if count_today >= campaign.daily_limit:
            return

        remaining = campaign.daily_limit - count_today

        # Get pending leads (including failed with retry_count < 1)
        pending_result = await db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign_id,
                (Lead.status == LeadStatus.pending)
                | ((Lead.status == LeadStatus.failed) & (Lead.retry_count < 1)),
            ).limit(remaining)
        )
        leads = pending_result.scalars().all()

        if not leads:
            # Check if all leads are processed
            all_pending = await db.execute(
                select(func.count(Lead.id)).where(
                    Lead.campaign_id == campaign_id,
                    Lead.status == LeadStatus.pending,
                )
            )
            if (all_pending.scalar() or 0) == 0:
                campaign.status = CampaignStatus.completed
                await db.commit()
            return

        cookies = json.loads(account.session_cookies)
        automation = LinkedInAutomation(headless=settings.headless)

        try:
            for lead in leads:
                result = await automation.send_connection_request(
                    cookies=cookies,
                    profile_url=lead.linkedin_url,
                    message=campaign.message_template,
                )

                status = result.get("status")
                lead.last_action_at = datetime.datetime.utcnow()

                if status == "sent":
                    lead.status = LeadStatus.invited
                elif status == "already_connected":
                    lead.status = LeadStatus.connected
                elif status in ("no_connect_button", "send_failed"):
                    if lead.retry_count >= 1:
                        lead.status = LeadStatus.skipped
                    else:
                        lead.status = LeadStatus.failed
                        lead.retry_count += 1
                elif status == "error":
                    lead.error_message = result.get("error", "Unknown error")
                    lead.retry_count += 1
                    if lead.retry_count >= 1:
                        lead.status = LeadStatus.failed
                else:
                    lead.status = LeadStatus.failed
                    lead.retry_count += 1

                await db.commit()

                # Random delay between actions
                delay = random.uniform(settings.min_delay, settings.max_delay)
                await asyncio.sleep(delay)

        finally:
            await automation.close()
