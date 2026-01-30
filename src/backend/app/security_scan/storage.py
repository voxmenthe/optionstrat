from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.security_scan.db import (
    SecurityAggregateValue,
    SecurityMetricValue,
    SecuritySet,
    SessionLocal,
)


MetricValueInput = dict[str, Any]


def compute_security_set_hash(tickers: Iterable[str]) -> tuple[str, list[str]]:
    canonical = sorted({ticker.strip() for ticker in tickers if ticker})
    joined = ",".join(canonical)
    set_hash = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return set_hash, canonical


def _get_session(existing: Session | None) -> tuple[Session, bool]:
    if existing is not None:
        return existing, False
    return SessionLocal(), True


def get_or_create_security_set(
    tickers: Iterable[str],
    db: Session | None = None,
) -> str:
    set_hash, canonical = compute_security_set_hash(tickers)
    session, owns_session = _get_session(db)
    try:
        existing = (
            session.query(SecuritySet)
            .filter(SecuritySet.set_hash == set_hash)
            .first()
        )
        if existing:
            return set_hash

        record = SecuritySet(
            set_hash=set_hash,
            tickers_json=json.dumps(canonical),
            ticker_count=len(canonical),
        )
        session.add(record)
        if owns_session:
            session.commit()
        else:
            session.flush()
        return set_hash
    except Exception:
        if session.is_active:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def upsert_security_metric_values(
    values: Iterable[MetricValueInput],
    db: Session | None = None,
) -> None:
    session, owns_session = _get_session(db)
    try:
        for value in values:
            ticker = value["ticker"]
            as_of_date = value["as_of_date"]
            interval = value.get("interval", "day")
            metric_key = value["metric_key"]
            record = (
                session.query(SecurityMetricValue)
                .filter(
                    SecurityMetricValue.ticker == ticker,
                    SecurityMetricValue.as_of_date == as_of_date,
                    SecurityMetricValue.interval == interval,
                    SecurityMetricValue.metric_key == metric_key,
                )
                .first()
            )
            if record:
                record.value = value.get("value")
                record.computed_at = value.get(
                    "computed_at", datetime.datetime.now(datetime.UTC)
                )
            else:
                session.add(
                    SecurityMetricValue(
                        ticker=ticker,
                        as_of_date=as_of_date,
                        interval=interval,
                        metric_key=metric_key,
                        value=value.get("value"),
                        computed_at=value.get(
                            "computed_at", datetime.datetime.now(datetime.UTC)
                        ),
                    )
                )
        if owns_session:
            session.commit()
        else:
            session.flush()
    except Exception:
        if session.is_active:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def fetch_security_metric_values(
    ticker: str,
    as_of_date: str,
    metric_keys: Iterable[str] | None = None,
    interval: str = "day",
    db: Session | None = None,
) -> dict[str, float | None]:
    session, owns_session = _get_session(db)
    try:
        query = (
            session.query(SecurityMetricValue)
            .filter(
                SecurityMetricValue.ticker == ticker,
                SecurityMetricValue.as_of_date == as_of_date,
                SecurityMetricValue.interval == interval,
            )
        )
        if metric_keys:
            query = query.filter(SecurityMetricValue.metric_key.in_(list(metric_keys)))
        rows = query.all()
        return {row.metric_key: row.value for row in rows}
    finally:
        if owns_session:
            session.close()


def upsert_security_aggregate_values(
    values: Iterable[MetricValueInput],
    db: Session | None = None,
) -> None:
    session, owns_session = _get_session(db)
    try:
        for value in values:
            set_hash = value["set_hash"]
            as_of_date = value["as_of_date"]
            interval = value.get("interval", "day")
            metric_key = value["metric_key"]
            record = (
                session.query(SecurityAggregateValue)
                .filter(
                    SecurityAggregateValue.set_hash == set_hash,
                    SecurityAggregateValue.as_of_date == as_of_date,
                    SecurityAggregateValue.interval == interval,
                    SecurityAggregateValue.metric_key == metric_key,
                )
                .first()
            )
            if record:
                record.value = value.get("value")
                record.valid_count = value.get("valid_count")
                record.missing_count = value.get("missing_count")
                record.computed_at = value.get(
                    "computed_at", datetime.datetime.now(datetime.UTC)
                )
            else:
                session.add(
                    SecurityAggregateValue(
                        set_hash=set_hash,
                        as_of_date=as_of_date,
                        interval=interval,
                        metric_key=metric_key,
                        value=value.get("value"),
                        valid_count=value.get("valid_count"),
                        missing_count=value.get("missing_count"),
                        computed_at=value.get(
                            "computed_at", datetime.datetime.now(datetime.UTC)
                        ),
                    )
                )
        if owns_session:
            session.commit()
        else:
            session.flush()
    except Exception:
        if session.is_active:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()
