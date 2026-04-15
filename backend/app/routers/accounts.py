from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Account, AccountStatus, User
from app.schemas import AccountCreate, AccountResponse
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
