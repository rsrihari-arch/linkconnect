import hashlib
import hmac
import json
import base64
import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.config import settings


def hash_password(password: str) -> str:
    salt = settings.secret_key
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat(),
    }
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(settings.secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def decode_token(token: str) -> Optional[dict]:
    try:
        data, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(settings.secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.b64decode(data))
        if datetime.datetime.fromisoformat(payload["exp"]) < datetime.datetime.utcnow():
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.execute(select(User).where(User.id == payload["user_id"])).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_optional_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns user if token present, None otherwise. For backward compat."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return get_current_user(authorization=authorization, db=db)
    except HTTPException:
        return None
