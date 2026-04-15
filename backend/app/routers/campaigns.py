from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Campaign, Lead, CampaignStatus, LeadStatus, Account
from app.schemas import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignStats

router = APIRouter()


async def _build_campaign_response(campaign: Campaign, db: AsyncSession) -> dict:
    stats_query = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.campaign_id == campaign.id)
        .group_by(Lead.status)
    )
    status_counts = {row[0]: row[1] for row in stats_query.all()}

    total = sum(status_counts.values())
    stats = CampaignStats(
        total=total,
        pending=status_counts.get(LeadStatus.pending, 0),
        invited=status_counts.get(LeadStatus.invited, 0),
        connected=status_counts.get(LeadStatus.connected, 0),
        failed=status_counts.get(LeadStatus.failed, 0),
        skipped=status_counts.get(LeadStatus.skipped, 0),
    )

    return CampaignResponse(
        id=campaign.id,
        account_id=campaign.account_id,
        name=campaign.name,
        daily_limit=campaign.daily_limit,
        message_template=campaign.message_template,
        status=campaign.status,
        created_at=campaign.created_at,
        stats=stats,
    )


@router.post("/", response_model=CampaignResponse)
async def create_campaign(data: CampaignCreate, db: AsyncSession = Depends(get_db)):
    account = await db.execute(select(Account).where(Account.id == data.account_id))
    if not account.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Account not found")

    campaign = Campaign(
        account_id=data.account_id,
        name=data.name,
        daily_limit=min(data.daily_limit, 30),
        message_template=data.message_template,
        status=CampaignStatus.stopped,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return await _build_campaign_response(campaign, db)


@router.get("/", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()
    return [await _build_campaign_response(c, db) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return await _build_campaign_response(campaign, db)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: int, data: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if data.name is not None:
        campaign.name = data.name
    if data.daily_limit is not None:
        campaign.daily_limit = min(data.daily_limit, 30)
    if data.message_template is not None:
        campaign.message_template = data.message_template

    await db.commit()
    await db.refresh(campaign)
    return await _build_campaign_response(campaign, db)


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    account = await db.execute(select(Account).where(Account.id == campaign.account_id))
    account = account.scalar_one_or_none()
    if not account or not account.session_cookies:
        raise HTTPException(status_code=400, detail="Account not logged in. Please login first.")

    campaign.status = CampaignStatus.active
    await db.commit()
    return {"message": "Campaign started", "campaign_id": campaign_id}


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.stopped
    await db.commit()
    return {"message": "Campaign stopped", "campaign_id": campaign_id}


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.delete(campaign)
    await db.commit()
    return {"message": "Campaign deleted"}
