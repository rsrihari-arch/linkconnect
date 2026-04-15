import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Account, AccountStatus
from app.schemas import AccountCreate, AccountResponse
from app.config import settings
from app.services.linkedin_automation import LinkedInAutomation

router = APIRouter()


@router.post("/", response_model=AccountResponse)
async def create_account(data: AccountCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Account).where(Account.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Account with this email already exists")

    fernet = settings.get_fernet()
    encrypted_pw = fernet.encrypt(data.password.encode()).decode()

    account = Account(
        email=data.email,
        encrypted_password=encrypted_pw,
        status=AccountStatus.login_required,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/{account_id}/login")
async def login_account(account_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    background_tasks.add_task(_perform_login, account_id)
    return {"message": "Login started in background", "account_id": account_id}


async def _perform_login(account_id: int):
    from app.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            return

        fernet = settings.get_fernet()
        password = fernet.decrypt(account.encrypted_password.encode()).decode()

        automation = LinkedInAutomation(headless=settings.headless)
        try:
            cookies = await automation.login(account.email, password)
            account.session_cookies = json.dumps(cookies)
            account.status = AccountStatus.active
        except Exception as e:
            account.status = AccountStatus.login_required
            print(f"Login failed for {account.email}: {e}")
        finally:
            await automation.close()

        await db.commit()


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    await db.commit()
    return {"message": "Account deleted"}
