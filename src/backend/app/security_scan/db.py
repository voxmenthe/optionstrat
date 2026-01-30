from __future__ import annotations

import datetime
import os
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[2]
SECURITY_SCAN_DB_PATH = BASE_DIR / "security_scan.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SECURITY_SCAN_DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_timeout=60,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SecuritySet(Base):
    """Database model for a canonical set of tickers used in scan aggregates."""

    __tablename__ = "security_sets"

    set_hash = Column(String, primary_key=True, index=True)
    tickers_json = Column(Text, nullable=False)
    ticker_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class SecurityMetricValue(Base):
    """Database model for per-security derived metric values (SMA/ROC)."""

    __tablename__ = "security_metric_values"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticker = Column(String, index=True, nullable=False)
    as_of_date = Column(String, index=True, nullable=False)
    interval = Column(String, nullable=False, default="day")
    metric_key = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "as_of_date",
            "interval",
            "metric_key",
            name="uq_security_metric_values_key",
        ),
    )


class SecurityAggregateValue(Base):
    """Database model for aggregate metric values per security-set hash."""

    __tablename__ = "security_aggregate_values"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    set_hash = Column(
        String, ForeignKey("security_sets.set_hash"), index=True, nullable=False
    )
    as_of_date = Column(String, index=True, nullable=False)
    interval = Column(String, nullable=False, default="day")
    metric_key = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    valid_count = Column(Integer, nullable=True)
    missing_count = Column(Integer, nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    __table_args__ = (
        UniqueConstraint(
            "set_hash",
            "as_of_date",
            "interval",
            "metric_key",
            name="uq_security_aggregate_values_key",
        ),
    )


if not os.path.exists(SECURITY_SCAN_DB_PATH):
    Base.metadata.create_all(bind=engine)
else:
    Base.metadata.create_all(bind=engine)
