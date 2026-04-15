import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Lead, Campaign, LeadStatus, User
from app.schemas import LeadResponse
from app.auth import get_current_user

router = APIRouter()


def _get_user_campaign(campaign_id: int, user: User, db: Session) -> Campaign:
    campaign = db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user.id)
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/{campaign_id}/leads/upload")
def upload_leads(
    campaign_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = _get_user_campaign(campaign_id, user, db)

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = file.file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    added = 0
    skipped = 0
    for row in reader:
        url = row.get("linkedin_url") or row.get("url") or row.get("profile_url") or row.get("LinkedIn URL")
        if not url:
            skipped += 1
            continue

        url = url.strip()
        if not url.startswith("http"):
            url = f"https://www.linkedin.com/in/{url}"

        existing = db.execute(
            select(Lead).where(Lead.campaign_id == campaign_id, Lead.linkedin_url == url)
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        name = row.get("name") or row.get("Name") or row.get("full_name")
        lead = Lead(
            campaign_id=campaign_id,
            linkedin_url=url,
            name=name.strip() if name else None,
            status=LeadStatus.pending,
        )
        db.add(lead)
        added += 1

    db.commit()
    return {"message": f"Uploaded {added} leads, skipped {skipped} duplicates"}


@router.post("/{campaign_id}/leads")
def add_single_lead(
    campaign_id: int,
    linkedin_url: str,
    name: str = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = _get_user_campaign(campaign_id, user, db)

    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://www.linkedin.com/in/{url}"

    existing = db.execute(
        select(Lead).where(Lead.campaign_id == campaign_id, Lead.linkedin_url == url)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Lead already exists in this campaign")

    lead = Lead(
        campaign_id=campaign_id,
        linkedin_url=url,
        name=name,
        status=LeadStatus.pending,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{campaign_id}/leads", response_model=list[LeadResponse])
def list_leads(
    campaign_id: int,
    status: LeadStatus = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = _get_user_campaign(campaign_id, user, db)

    query = select(Lead).where(Lead.campaign_id == campaign_id)
    if status:
        query = query.where(Lead.status == status)
    query = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit)

    result = db.execute(query)
    return result.scalars().all()


@router.delete("/{campaign_id}/leads/{lead_id}")
def delete_lead(campaign_id: int, lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = _get_user_campaign(campaign_id, user, db)

    lead = db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.campaign_id == campaign_id)
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"message": "Lead deleted"}
