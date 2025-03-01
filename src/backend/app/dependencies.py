from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Generator

from .database import SessionLocal
from .services.market_data_provider import MarketDataProvider
from .services.yfinance_provider import YFinanceProvider
from .services.polygon_provider import PolygonProvider
from .services.option_pricer import OptionPricer
from .services.scenario_engine import ScenarioEngine
from .services.volatility_service import VolatilityService

# Database dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Market data provider dependency
def get_market_data_service() -> MarketDataProvider:
    # Use YFinance provider by default, could be configurable
    return YFinanceProvider()

# Option pricer dependency
def get_option_pricer() -> OptionPricer:
    return OptionPricer()

# Scenario engine dependency
def get_scenario_engine(
    market_data_service: MarketDataProvider = Depends(get_market_data_service),
    option_pricer: OptionPricer = Depends(get_option_pricer)
) -> ScenarioEngine:
    return ScenarioEngine(market_data_service, option_pricer)

# Volatility service dependency
def get_volatility_service(
    market_data_service: MarketDataProvider = Depends(get_market_data_service)
) -> VolatilityService:
    return VolatilityService(market_data_service)
