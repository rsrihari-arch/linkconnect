import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/linkedin_automation")
connect_args = {}

# Convert standard URL to pg8000 format
if "postgresql://" in db_url and "+" not in db_url.split("://")[0]:
    db_url = db_url.replace("postgresql://", "postgresql+pg8000://")

# Handle sslmode parameter (pg8000 uses ssl_context)
if "sslmode=" in db_url:
    db_url = db_url.split("?")[0]
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl_context"] = ssl_context

engine = create_engine(db_url, echo=False, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

_tables_created = False


class Base(DeclarativeBase):
    pass


def get_db():
    global _tables_created
    if not _tables_created:
        init_db()
        _tables_created = True
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
