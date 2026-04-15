import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Lead, Campaign, LeadStatus
from app.schemas import LeadResponse

router = APIRouter()


@router.post("/{campaign_id}/leads/upload")
async def upload_leads(
    campaign_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
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

        existing = await db.execute(
            select(Lead).where(Lead.campaign_id == campaign_id, Lead.linkedin_url == url)
        )
        if existing.scalar_one_or_none():
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

    await db.commit()
    return {"message": f"Uploaded {added} leads, skipped {skipped} duplicates"}


@router.post("/{campaign_id}/leads")
async def add_single_lead(
    campaign_id: int,
    linkedin_url: str,
    name: str = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Campaign not found")

    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://www.linkedin.com/in/{url}"

    existing = await db.execute(
        select(Lead).where(Lead.campaign_id == campaign_id, Lead.linkedin_url == url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Lead already exists in this campaign")

    lead = Lead(
        campaign_id=campaign_id,
        linkedin_url=url,
        name=name,
        status=LeadStatus.pending,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{campaign_id}/leads", response_model=list[LeadResponse])
async def list_leads(
    campaign_id: int,
    status: LeadStatus = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead).where(Lead.campaign_id == campaign_id)
    if status:
        query = query.where(Lead.status == status)
    query = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{campaign_id}/leads/{lead_id}")
async def delete_lead(campaign_id: int, lead_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.campaign_id == campaign_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    await db.commit()
    return {"message": "Lead deleted"}
