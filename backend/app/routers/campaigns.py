from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Campaign, Lead, CampaignStatus, LeadStatus, Account, User, FollowUpStep, FollowUpLog
from app.schemas import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignStats
from app.auth import get_current_user

router = APIRouter()


def _build_stats_for_campaigns(campaign_ids: list, db: Session) -> dict:
    """Batch-fetch all stats for multiple campaigns in 3 queries instead of 3N."""
    if not campaign_ids:
        return {}

    # 1. Lead status counts for all campaigns at once
    lead_counts = db.execute(
        select(Lead.campaign_id, Lead.status, func.count(Lead.id))
        .where(Lead.campaign_id.in_(campaign_ids))
        .group_by(Lead.campaign_id, Lead.status)
    ).all()

    # 2. Follow-up sent counts for all campaigns at once
    fu_sent = db.execute(
        select(FollowUpStep.campaign_id, func.count(FollowUpLog.id))
        .join(FollowUpLog, FollowUpLog.step_id == FollowUpStep.id)
        .where(FollowUpStep.campaign_id.in_(campaign_ids), FollowUpLog.status == "sent")
        .group_by(FollowUpStep.campaign_id)
    ).all()

    # 3. Follow-up failed counts for all campaigns at once
    fu_failed = db.execute(
        select(FollowUpStep.campaign_id, func.count(FollowUpLog.id))
        .join(FollowUpLog, FollowUpLog.step_id == FollowUpStep.id)
        .where(FollowUpStep.campaign_id.in_(campaign_ids), FollowUpLog.status == "failed")
        .group_by(FollowUpStep.campaign_id)
    ).all()

    # Assemble results by campaign_id
    by_campaign: dict = {cid: {"counts": {}, "fu_sent": 0, "fu_failed": 0} for cid in campaign_ids}
    for cid, status, count in lead_counts:
        by_campaign[cid]["counts"][status] = count
    for cid, count in fu_sent:
        by_campaign[cid]["fu_sent"] = count
    for cid, count in fu_failed:
        by_campaign[cid]["fu_failed"] = count

    return by_campaign


def _make_campaign_response(campaign: Campaign, stats_data: dict) -> CampaignResponse:
    counts = stats_data.get("counts", {})
    total = sum(counts.values())
    stats = CampaignStats(
        total=total,
        pending=counts.get(LeadStatus.pending, 0),
        invited=counts.get(LeadStatus.invited, 0),
        connected=counts.get(LeadStatus.connected, 0),
        failed=counts.get(LeadStatus.failed, 0),
        skipped=counts.get(LeadStatus.skipped, 0),
        followups_sent=stats_data.get("fu_sent", 0),
        followups_failed=stats_data.get("fu_failed", 0),
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


def _build_campaign_response(campaign: Campaign, db: Session) -> CampaignResponse:
    """Single-campaign response (used for create/update/get endpoints)."""
    batch = _build_stats_for_campaigns([campaign.id], db)
    return _make_campaign_response(campaign, batch.get(campaign.id, {}))


@router.post("/", response_model=CampaignResponse)
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.execute(
        select(Account).where(Account.id == data.account_id, Account.user_id == user.id)
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    campaign = Campaign(
        user_id=user.id,
        account_id=data.account_id,
        name=data.name,
        daily_limit=min(data.daily_limit, 30),
        message_template=data.message_template,
        status=CampaignStatus.stopped,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _build_campaign_response(campaign, db)


@router.get("/", response_model=List[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaigns = db.execute(
        select(Campaign).where(Campaign.user_id == user.id).order_by(Campaign.created_at.desc())
    ).scalars().all()

    if not campaigns:
        return []

    # Fetch all stats in 3 queries regardless of campaign count
    campaign_ids = [c.id for c in campaigns]
    stats_by_campaign = _build_stats_for_campaigns(campaign_ids, db)

    return [_make_campaign_response(c, stats_by_campaign.get(c.id, {})) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _build_campaign_response(campaign, db)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(campaign_id: int, data: CampaignUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if data.name is not None:
        campaign.name = data.name
    if data.daily_limit is not None:
        campaign.daily_limit = min(data.daily_limit, 30)
    if data.message_template is not None:
        campaign.message_template = data.message_template

    db.commit()
    db.refresh(campaign)
    return _build_campaign_response(campaign, db)


@router.post("/{campaign_id}/start")
def start_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.active
    db.commit()
    return {"message": "Campaign started", "campaign_id": campaign_id}


@router.post("/{campaign_id}/stop")
def stop_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.stopped
    db.commit()
    return {"message": "Campaign stopped", "campaign_id": campaign_id}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != CampaignStatus.active:
        raise HTTPException(status_code=400, detail="Only active campaigns can be paused")
    campaign.status = CampaignStatus.paused
    db.commit()
    return {"message": "Campaign paused", "campaign_id": campaign_id}


@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != CampaignStatus.paused:
        raise HTTPException(status_code=400, detail="Only paused campaigns can be resumed")
    campaign.status = CampaignStatus.active
    db.commit()
    return {"message": "Campaign resumed", "campaign_id": campaign_id}


@router.post("/{campaign_id}/reset-failed-leads")
def reset_failed_leads(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Reset failed/skipped leads back to pending so they can be retried."""
    from sqlalchemy import update as sa_update
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = db.execute(
        sa_update(Lead)
        .where(Lead.campaign_id == campaign_id, Lead.status.in_([LeadStatus.failed, LeadStatus.skipped]))
        .values(status=LeadStatus.pending, retry_count=0, error_message=None)
    )
    db.commit()
    count = result.rowcount
    return {"message": f"{count} lead(s) reset to pending", "count": count}


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"message": "Campaign deleted"}
