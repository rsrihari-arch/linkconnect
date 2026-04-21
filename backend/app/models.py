import datetime
import random
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    login_required = "login_required"
    verifying = "verifying"


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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")


class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    @staticmethod
    def generate_code() -> str:
        return str(random.randint(100000, 999999))


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    session_cookies = Column(Text, nullable=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.login_required)
    verification_code = Column(String(20), nullable=True)
    login_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    campaigns = relationship("Campaign", back_populates="account", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String(255), nullable=False)
    daily_limit = Column(Integer, default=20)
    message_template = Column(Text, nullable=True)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.stopped)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="campaigns")
    account = relationship("Account", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")
    follow_up_steps = relationship("FollowUpStep", back_populates="campaign", cascade="all, delete-orphan", order_by="FollowUpStep.step_order")


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
    connected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    campaign = relationship("Campaign", back_populates="leads")
    follow_up_logs = relationship("FollowUpLog", back_populates="lead", cascade="all, delete-orphan")


class FollowUpStep(Base):
    __tablename__ = "follow_up_steps"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    step_order = Column(Integer, nullable=False, default=1)
    message_template = Column(Text, nullable=False)
    delay_days = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    campaign = relationship("Campaign", back_populates="follow_up_steps")


class FollowUpLog(Base):
    __tablename__ = "follow_up_logs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("follow_up_steps.id"), nullable=False)
    status = Column(String(20), default="sent")
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)

    lead = relationship("Lead", back_populates="follow_up_logs")
    step = relationship("FollowUpStep")
