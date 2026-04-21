from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Campaign, FollowUpStep, FollowUpLog, Lead, LeadStatus, User
from app.schemas import FollowUpStepCreate, FollowUpStepUpdate, FollowUpStepResponse
from app.auth import get_current_user

router = APIRouter()


def _get_user_campaign(campaign_id: int, db: Session, user: User) -> Campaign:
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/followups", response_model=list[FollowUpStepResponse])
def list_followup_steps(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_user_campaign(campaign_id, db, user)
    steps = db.execute(
        select(FollowUpStep)
        .where(FollowUpStep.campaign_id == campaign_id)
        .order_by(FollowUpStep.step_order)
    ).scalars().all()
    return steps


@router.post("/{campaign_id}/followups", response_model=FollowUpStepResponse)
def create_followup_step(campaign_id: int, data: FollowUpStepCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_user_campaign(campaign_id, db, user)

    # Get next step order
    max_order = db.execute(
        select(func.max(FollowUpStep.step_order)).where(FollowUpStep.campaign_id == campaign_id)
    ).scalar() or 0

    step = FollowUpStep(
        campaign_id=campaign_id,
        step_order=max_order + 1,
        message_template=data.message_template,
        delay_days=max(data.delay_days, 1),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.put("/{campaign_id}/followups/{step_id}", response_model=FollowUpStepResponse)
def update_followup_step(campaign_id: int, step_id: int, data: FollowUpStepUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_user_campaign(campaign_id, db, user)
    step = db.execute(
        select(FollowUpStep).where(FollowUpStep.id == step_id, FollowUpStep.campaign_id == campaign_id)
    ).scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Follow-up step not found")

    if data.message_template is not None:
        step.message_template = data.message_template
    if data.delay_days is not None:
        step.delay_days = max(data.delay_days, 1)

    db.commit()
    db.refresh(step)
    return step


@router.delete("/{campaign_id}/followups/{step_id}")
def delete_followup_step(campaign_id: int, step_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_user_campaign(campaign_id, db, user)
    step = db.execute(
        select(FollowUpStep).where(FollowUpStep.id == step_id, FollowUpStep.campaign_id == campaign_id)
    ).scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Follow-up step not found")

    db.delete(step)
    db.commit()

    # Reorder remaining steps
    remaining = db.execute(
        select(FollowUpStep)
        .where(FollowUpStep.campaign_id == campaign_id)
        .order_by(FollowUpStep.step_order)
    ).scalars().all()
    for i, s in enumerate(remaining):
        s.step_order = i + 1
    db.commit()

    return {"message": "Follow-up step deleted"}


@router.get("/{campaign_id}/followups/stats")
def followup_stats(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_user_campaign(campaign_id, db, user)

    steps = db.execute(
        select(FollowUpStep).where(FollowUpStep.campaign_id == campaign_id).order_by(FollowUpStep.step_order)
    ).scalars().all()

    result = []
    for step in steps:
        sent = db.execute(
            select(func.count(FollowUpLog.id)).where(
                FollowUpLog.step_id == step.id,
                FollowUpLog.status == "sent",
            )
        ).scalar() or 0
        failed = db.execute(
            select(func.count(FollowUpLog.id)).where(
                FollowUpLog.step_id == step.id,
                FollowUpLog.status == "failed",
            )
        ).scalar() or 0
        result.append({
            "step_id": step.id,
            "step_order": step.step_order,
            "delay_days": step.delay_days,
            "sent": sent,
            "failed": failed,
        })

    return result
