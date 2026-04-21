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


class AccountVerifyCode(BaseModel):
    code: str


class AccountResponse(BaseModel):
    id: int
    email: str
    status: AccountStatus
    login_error: Optional[str] = None
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
    followups_sent: int = 0
    followups_failed: int = 0


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
    connected_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Follow-Up Schemas ---

class FollowUpStepCreate(BaseModel):
    message_template: str
    delay_days: int = 1


class FollowUpStepUpdate(BaseModel):
    message_template: Optional[str] = None
    delay_days: Optional[int] = None


class FollowUpStepResponse(BaseModel):
    id: int
    campaign_id: int
    step_order: int
    message_template: str
    delay_days: int
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpLogResponse(BaseModel):
    id: int
    lead_id: int
    step_id: int
    status: str
    error_message: Optional[str]
    sent_at: datetime

    class Config:
        from_attributes = True
