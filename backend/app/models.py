import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    login_required = "login_required"


class CampaignStatus(str, enum.Enum):
    active = "active"
    stopped = "stopped"
    completed = "completed"
    paused = "paused"


class LeadStatus(str, enum.Enum):
    pending = "pending"
    invited = "invited"
    connected = "connected"
    failed = "failed"
    skipped = "skipped"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    encrypted_password = Column(Text, nullable=False)
    session_cookies = Column(Text, nullable=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.login_required)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    campaigns = relationship("Campaign", back_populates="account", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String(255), nullable=False)
    daily_limit = Column(Integer, default=20)
    message_template = Column(Text, nullable=True)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.stopped)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    account = relationship("Account", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    linkedin_url = Column(String(500), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.pending)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    last_action_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    campaign = relationship("Campaign", back_populates="leads")
