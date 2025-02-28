from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.database import get_db, DBPosition
from app.models.schemas import ScenarioAnalysisRequest
from app.services.scenario_engine import ScenarioEngine
from app.services.market_data import MarketDataService
from app.services.option_pricing import OptionPricer

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
    responses={404: {"description": "Not found"}},
)

scenario_engine = ScenarioEngine()
market_data_service = MarketDataService()

# Create dependency function for OptionPricer
def get_option_pricer():
    """Dependency to get the option pricer service."""
    return OptionPricer()

# Define a Pydantic model for the price vs volatility request
class VolatilityRange(BaseModel):
    min: float = 0.1
    max: float = 0.5
    steps: int = 5

class PriceVsVolatilityRequest(BaseModel):
    option_type: str
    strike: float
    expiration_date: str
    spot_price: float
    volatility_range: VolatilityRange = Field(default_factory=lambda: VolatilityRange())
    risk_free_rate: float = 0.05
    dividend_yield: float = 0.0
    american: bool = False

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


@router.post("/price-vs-volatility", response_model=Dict)
def price_vs_volatility_scenario(
    request: PriceVsVolatilityRequest,
    option_pricer: OptionPricer = Depends(get_option_pricer)
):
    """
    Calculate option prices and Greeks across different volatility values.
    
    This endpoint is specifically for a single option, not a position or portfolio.
    """
    try:
        # Debug prints
        print(f"Request received: {request}")
        print(f"Option pricer instance: {option_pricer}")
        
        # Calculate volatility steps
        min_vol = request.volatility_range.min
        max_vol = request.volatility_range.max
        steps = request.volatility_range.steps
        
        volatilities = [min_vol + (max_vol - min_vol) * i / (steps - 1) for i in range(steps)]
        print(f"Volatilities: {volatilities}")
        
        # Calculate prices and Greeks for each volatility
        prices = []
        deltas = []
        gammas = []
        thetas = []
        vegas = []
        rhos = []
        
        for vol in volatilities:
            try:
                print(f"Processing volatility: {vol}")
                # Call the price_option method with the correct parameters
                result = option_pricer.price_option(
                    option_type=request.option_type,
                    strike=request.strike,
                    expiration_date=request.expiration_date,
                    spot_price=request.spot_price,
                    volatility=vol,
                    risk_free_rate=request.risk_free_rate,
                    dividend_yield=request.dividend_yield,
                    american=request.american
                )
                
                print(f"Result for volatility {vol}: {result}")
                
                # Extract the values from the result
                prices.append(result.get("price", 0.0))
                deltas.append(result.get("delta", 0.0))
                gammas.append(result.get("gamma", 0.0))
                thetas.append(result.get("theta", 0.0))
                vegas.append(result.get("vega", 0.0))
                rhos.append(result.get("rho", 0.0))
            except Exception as e:
                print(f"Error pricing option with volatility {vol}: {str(e)}")
                import traceback
                print(traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"Error pricing option with volatility {vol}: {str(e)}")
        
        # Return the results in the expected format
        response_data = {
            "volatilities": volatilities,
            "prices": prices,
            "deltas": deltas,
            "gammas": gammas,
            "thetas": thetas,
            "vegas": vegas,
            "rhos": rhos
        }
        print(f"Response data: {response_data}")
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in price_vs_volatility_scenario: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error calculating price vs volatility: {str(e)}")


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