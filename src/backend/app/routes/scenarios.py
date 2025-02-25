from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.models.database import get_db, DBPosition
from app.models.schemas import ScenarioAnalysisRequest
from app.services.scenario_engine import ScenarioEngine
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
    responses={404: {"description": "Not found"}},
)

scenario_engine = ScenarioEngine()
market_data_service = MarketDataService()


@router.post("/price-vs-vol", response_model=Dict)
def price_vs_volatility_surface(
    request: ScenarioAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a price vs. volatility surface for a set of positions.
    
    This calculates the P&L of the positions across different price and volatility scenarios.
    """
    # Get positions from database
    positions = db.query(DBPosition).filter(DBPosition.id.in_(request.position_ids)).all()
    
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    
    # Convert SQLAlchemy models to dictionaries
    position_dicts = []
    for pos in positions:
        position_dicts.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "expiration": pos.expiration,
            "strike": pos.strike,
            "option_type": pos.option_type,
            "action": pos.action,
            "quantity": pos.quantity
        })
    
    # Get current price and volatility
    # Assuming all positions have the same underlying ticker
    ticker = positions[0].ticker
    try:
        current_price = market_data_service.get_stock_price(ticker)
        current_vol = market_data_service.get_implied_volatility(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Generate surface
    try:
        surface = scenario_engine.price_vs_vol_surface(
            positions=position_dicts,
            current_price=current_price,
            current_vol=current_vol,
            price_range=request.price_range,
            vol_range=request.volatility_range
        )
        
        return surface
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating surface: {str(e)}")


@router.post("/price-vs-time", response_model=Dict)
def price_vs_time_surface(
    request: ScenarioAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a price vs. time surface for a set of positions.
    
    This calculates the P&L of the positions across different price and time scenarios.
    """
    # Get positions from database
    positions = db.query(DBPosition).filter(DBPosition.id.in_(request.position_ids)).all()
    
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    
    # Convert SQLAlchemy models to dictionaries
    position_dicts = []
    for pos in positions:
        position_dicts.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "expiration": pos.expiration,
            "strike": pos.strike,
            "option_type": pos.option_type,
            "action": pos.action,
            "quantity": pos.quantity
        })
    
    # Get current price and volatility
    # Assuming all positions have the same underlying ticker
    ticker = positions[0].ticker
    try:
        current_price = market_data_service.get_stock_price(ticker)
        current_vol = market_data_service.get_implied_volatility(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Generate surface
    try:
        surface = scenario_engine.price_vs_time_surface(
            positions=position_dicts,
            current_price=current_price,
            current_vol=current_vol,
            price_range=request.price_range,
            days_range=request.days_to_expiry_range
        )
        
        return surface
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating surface: {str(e)}")


@router.post("/greeks-profile", response_model=Dict)
def greeks_profile(
    request: ScenarioAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Greeks profiles for a set of positions.
    
    This calculates how the Greeks change across different price scenarios.
    """
    # Get positions from database
    positions = db.query(DBPosition).filter(DBPosition.id.in_(request.position_ids)).all()
    
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    
    # Convert SQLAlchemy models to dictionaries
    position_dicts = []
    for pos in positions:
        position_dicts.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "expiration": pos.expiration,
            "strike": pos.strike,
            "option_type": pos.option_type,
            "action": pos.action,
            "quantity": pos.quantity
        })
    
    # Get current price and volatility
    # Assuming all positions have the same underlying ticker
    ticker = positions[0].ticker
    try:
        current_price = market_data_service.get_stock_price(ticker)
        current_vol = market_data_service.get_implied_volatility(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Generate Greeks profile
    try:
        profile = scenario_engine.calculate_greeks_profile(
            positions=position_dicts,
            current_price=current_price,
            current_vol=current_vol,
            price_range=request.price_range
        )
        
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Greeks profile: {str(e)}")


@router.get("/strategy/{strategy_name}", response_model=Dict)
def get_strategy_analysis(
    strategy_name: str,
    ticker: str,
    strike: float,
    days_to_expiry: int,
    volatility: Optional[float] = None
):
    """
    Get pre-defined analysis for common option strategies.
    
    Supported strategies: long_call, long_put, covered_call, protective_put, 
    bull_call_spread, bear_put_spread, straddle, strangle, butterfly, iron_condor
    """
    # This is a placeholder for strategy analysis
    # In a real implementation, you would calculate the P&L and Greeks for the strategy
    
    # Get current price and volatility
    try:
        current_price = market_data_service.get_stock_price(ticker)
        current_vol = volatility or market_data_service.get_implied_volatility(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Create positions based on strategy
    positions = []
    
    if strategy_name == "long_call":
        positions.append({
            "id": "1",
            "ticker": ticker,
            "expiration": days_to_expiry,
            "strike": strike,
            "option_type": "call",
            "action": "buy",
            "quantity": 1
        })
    elif strategy_name == "long_put":
        positions.append({
            "id": "1",
            "ticker": ticker,
            "expiration": days_to_expiry,
            "strike": strike,
            "option_type": "put",
            "action": "buy",
            "quantity": 1
        })
    elif strategy_name == "covered_call":
        # Long stock + short call
        positions.append({
            "id": "1",
            "ticker": ticker,
            "expiration": days_to_expiry,
            "strike": strike,
            "option_type": "call",
            "action": "sell",
            "quantity": 1
        })
    elif strategy_name == "bull_call_spread":
        # Long call at lower strike + short call at higher strike
        positions.append({
            "id": "1",
            "ticker": ticker,
            "expiration": days_to_expiry,
            "strike": strike,
            "option_type": "call",
            "action": "buy",
            "quantity": 1
        })
        positions.append({
            "id": "2",
            "ticker": ticker,
            "expiration": days_to_expiry,
            "strike": strike * 1.05,  # 5% higher strike
            "option_type": "call",
            "action": "sell",
            "quantity": 1
        })
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported strategy: {strategy_name}")
    
    # Generate analysis
    try:
        # Price vs. volatility surface
        price_vol_surface = scenario_engine.price_vs_vol_surface(
            positions=positions,
            current_price=current_price,
            current_vol=current_vol
        )
        
        # Greeks profile
        greeks_profile = scenario_engine.calculate_greeks_profile(
            positions=positions,
            current_price=current_price,
            current_vol=current_vol
        )
        
        return {
            "strategy": strategy_name,
            "ticker": ticker,
            "current_price": current_price,
            "current_vol": current_vol,
            "price_vol_surface": price_vol_surface,
            "greeks_profile": greeks_profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating strategy analysis: {str(e)}") 