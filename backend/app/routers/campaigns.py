from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Campaign, Lead, CampaignStatus, LeadStatus, Account, User, FollowUpStep, FollowUpLog
from app.schemas import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignStats
from app.auth import get_current_user

router = APIRouter()


def _build_campaign_response(campaign: Campaign, db: Session) -> CampaignResponse:
    stats_query = db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.campaign_id == campaign.id)
        .group_by(Lead.status)
    )
    status_counts = {row[0]: row[1] for row in stats_query.all()}

    total = sum(status_counts.values())

    # Count follow-up messages sent for this campaign
    followup_sent = db.execute(
        select(func.count(FollowUpLog.id)).where(
            FollowUpLog.step_id.in_(
                select(FollowUpStep.id).where(FollowUpStep.campaign_id == campaign.id)
            ),
            FollowUpLog.status == "sent",
        )
    ).scalar() or 0

    followup_failed = db.execute(
        select(func.count(FollowUpLog.id)).where(
            FollowUpLog.step_id.in_(
                select(FollowUpStep.id).where(FollowUpStep.campaign_id == campaign.id)
            ),
            FollowUpLog.status == "failed",
        )
    ).scalar() or 0

    stats = CampaignStats(
        total=total,
        pending=status_counts.get(LeadStatus.pending, 0),
        invited=status_counts.get(LeadStatus.invited, 0),
        connected=status_counts.get(LeadStatus.connected, 0),
        failed=status_counts.get(LeadStatus.failed, 0),
        skipped=status_counts.get(LeadStatus.skipped, 0),
        followups_sent=followup_sent,
        followups_failed=followup_failed,
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


@router.get("/", response_model=list[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = db.execute(
        select(Campaign).where(Campaign.user_id == user.id).order_by(Campaign.created_at.desc())
    )
    campaigns = result.scalars().all()
    return [_build_campaign_response(c, db) for c in campaigns]


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
