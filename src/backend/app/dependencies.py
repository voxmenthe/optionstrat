from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Generator
import logging

from .models.database import SessionLocal
from .services.market_data import MarketDataService
from .services.option_chain_service import OptionChainService

logger = logging.getLogger(__name__)


# Database dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Market data service dependency
def get_market_data_service() -> MarketDataService:
    logger.debug("Creating new MarketDataService instance")
    return MarketDataService()

# Option chain service dependency
def get_option_chain_service(
    market_data_service: MarketDataService = Depends(get_market_data_service)
) -> OptionChainService:
    logger.debug("Creating new OptionChainService instance with MarketDataService")
    return OptionChainService(market_data_service)
