import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import User, OTP
from app.auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter()


class SignupRequest(BaseModel):
    email: str
    password: str


class VerifyOTPRequest(BaseModel):
    email: str
    code: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if existing and existing.is_verified:
        raise HTTPException(status_code=400, detail="Email already registered")

    if existing and not existing.is_verified:
        user = existing
        user.password_hash = hash_password(data.password)
    else:
        user = User(email=data.email, password_hash=hash_password(data.password))
        db.add(user)
        db.flush()

    # Generate OTP
    otp = OTP(
        user_id=user.id,
        code=OTP.generate_code(),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    db.add(otp)
    db.commit()

    # For now, return OTP in response (replace with email sending later)
    return {
        "message": "OTP sent to your email",
        "otp_preview": otp.code,  # Remove this when email is configured
    }


@router.post("/verify")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = db.execute(
        select(OTP).where(
            OTP.user_id == user.id,
            OTP.code == data.code,
            OTP.used == False,
            OTP.expires_at >= datetime.datetime.utcnow(),
        ).order_by(OTP.id.desc())
    ).scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    otp.used = True
    user.is_verified = True
    db.commit()

    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email}}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please sign up again to get a new OTP.")

    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email}}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}
