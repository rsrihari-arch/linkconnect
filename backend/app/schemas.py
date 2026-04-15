from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from app.models import AccountStatus, CampaignStatus, LeadStatus


# --- Account Schemas ---

class AccountCreate(BaseModel):
    email: str
    password: str


class AccountCreateWithCookies(BaseModel):
    email: str
    cookies: str


class AccountResponse(BaseModel):
    id: int
    email: str
    status: AccountStatus
    created_at: datetime

    class Config:
        from_attributes = True


# --- Campaign Schemas ---

class CampaignCreate(BaseModel):
    account_id: int
    name: str
    daily_limit: int = 20
    message_template: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    daily_limit: Optional[int] = None
    message_template: Optional[str] = None


class CampaignStats(BaseModel):
    total: int = 0
    pending: int = 0
    invited: int = 0
    connected: int = 0
    failed: int = 0
    skipped: int = 0


class CampaignResponse(BaseModel):
    id: int
    account_id: int
    name: str
    daily_limit: int
    message_template: Optional[str]
    status: CampaignStatus
    created_at: datetime
    stats: Optional[CampaignStats] = None

    class Config:
        from_attributes = True


# --- Lead Schemas ---

class LeadCreate(BaseModel):
    linkedin_url: str
    name: Optional[str] = None


class LeadResponse(BaseModel):
    id: int
    campaign_id: int
    linkedin_url: str
    name: Optional[str]
    status: LeadStatus
    retry_count: int
    error_message: Optional[str]
    last_action_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
