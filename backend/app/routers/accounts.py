import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Account, AccountStatus, User
from app.schemas import AccountCreate, AccountCreateWithCookies, AccountResponse
from app.config import settings
from app.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=AccountResponse)
def create_account(data: AccountCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.execute(
        select(Account).where(Account.email == data.email, Account.user_id == user.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Account with this email already exists")

    encrypted_pw = settings.encrypt(data.password)

    account = Account(
        user_id=user.id,
        email=data.email,
        encrypted_password=encrypted_pw,
        status=AccountStatus.login_required,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.post("/cookies", response_model=AccountResponse)
def create_account_with_cookies(data: AccountCreateWithCookies, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Connect a LinkedIn account by pasting cookies from the browser."""
    existing = db.execute(
        select(Account).where(Account.email == data.email, Account.user_id == user.id)
    ).scalar_one_or_none()

    # Parse and validate cookies
    try:
        cookies_raw = data.cookies.strip()
        # Support JSON array format (from browser extensions)
        if cookies_raw.startswith("["):
            cookies = json.loads(cookies_raw)
        else:
            # Support header format: name=value; name2=value2
            cookies = []
            for pair in cookies_raw.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    cookies.append({"name": name.strip(), "value": value.strip(), "domain": ".linkedin.com", "path": "/"})

        if not cookies:
            raise ValueError("No cookies found")

        # Check for li_at cookie (LinkedIn session)
        li_at = next((c for c in cookies if c.get("name") == "li_at"), None)
        if not li_at:
            raise HTTPException(status_code=400, detail="Missing 'li_at' cookie. Make sure you're logged into LinkedIn and copy all cookies.")

        cookies_json = json.dumps(cookies)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid cookie format. Paste cookies as JSON array or as 'name=value; name2=value2' format.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse cookies: {str(e)}")

    if existing:
        # Update existing account with new cookies
        existing.session_cookies = cookies_json
        existing.status = AccountStatus.active
        db.commit()
        db.refresh(existing)
        return existing

    account = Account(
        user_id=user.id,
        email=data.email,
        encrypted_password="cookie-auth",  # No password needed for cookie auth
        session_cookies=cookies_json,
        status=AccountStatus.active,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = db.execute(
        select(Account).where(Account.user_id == user.id).order_by(Account.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/{account_id}/login")
def login_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Login queued. Run the automation worker locally to process logins.", "account_id": account_id}


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"message": "Account deleted"}
