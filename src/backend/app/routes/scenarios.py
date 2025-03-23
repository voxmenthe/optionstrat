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

# Define models for scenario requests
class PriceRange(BaseModel):
    min: float
    max: float 
    steps: int = 50

class VolatilityRange(BaseModel):
    min: float = 0.1
    max: float = 0.5
    steps: int = 5

class PositionInput(BaseModel):
    ticker: str
    expiration: str
    strike: float
    option_type: str
    action: str
    quantity: int
    premium: Optional[float] = None

class PriceScenarioRequest(BaseModel):
    positions: List[PositionInput]
    price_range: Optional[PriceRange] = None
    base_volatility: Optional[float] = None
    risk_free_rate: Optional[float] = 0.05
    dividend_yield: Optional[float] = 0.0

class PriceVsVolatilityRequest(BaseModel):
    option_type: str
    strike: float
    expiration_date: str
    spot_price: float
    volatility_range: VolatilityRange = Field(default_factory=lambda: VolatilityRange())
    risk_free_rate: float = 0.05
    dividend_yield: float = 0.0
    american: bool = False

@router.post("/price", response_model=Dict)
async def analyze_price_scenario(
    request: PriceScenarioRequest,
    option_pricer: OptionPricer = Depends(get_option_pricer)
):
    """
    Analyze how option positions perform across different underlying price scenarios.
    
    Returns price points with option values and Greeks at each price point.
    """
    try:
        # Log the incoming request
        print(f"Price scenario request received: {len(request.positions)} positions")
        
        # Extract positions from request
        positions = request.positions
        
        if not positions:
            raise HTTPException(status_code=400, detail="No positions provided")
        
        # Get reference ticker from first position
        ticker = positions[0].ticker
        
        # Get current market data
        try:
            current_price = market_data_service.get_stock_price(ticker)
            current_vol = market_data_service.get_implied_volatility(ticker)
            
            # Use provided volatility if available, otherwise use market data
            volatility = request.base_volatility if request.base_volatility is not None else current_vol
            
        except Exception as e:
            print(f"Warning: Could not fetch market data: {e}")
            # Estimate current price as average of strikes if market data unavailable
            current_price = sum([p.strike for p in positions]) / len(positions)
            volatility = request.base_volatility if request.base_volatility is not None else 0.3  # Default 30% vol
        
        # Set up price range
        if request.price_range:
            price_min = request.price_range.min
            price_max = request.price_range.max
            steps = request.price_range.steps
        else:
            # Default: 50% below to 50% above current price with 50 steps
            price_min = current_price * 0.5
            price_max = current_price * 1.5
            steps = 50
        
        # Generate price points
        price_points = []
        for i in range(steps + 1):
            spot_price = price_min + (price_max - price_min) * i / steps
            
            # Initialize aggregated values
            total_value = 0
            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            total_rho = 0
            
            # Calculate value and Greeks for each position at this price
            for position in positions:
                # Get option pricing
                result = option_pricer.price_option(
                    option_type=position.option_type,
                    strike=position.strike,
                    expiration_date=position.expiration,
                    spot_price=spot_price,
                    volatility=volatility,
                    risk_free_rate=request.risk_free_rate,
                    dividend_yield=request.dividend_yield,
                    american=True  # Default to American options
                )
                
                # Calculate value based on position action and quantity
                multiplier = position.quantity * (1 if position.action == "buy" else -1)
                position_value = result.get("price", 0) * multiplier
                
                # If premium is provided, subtract it for buys, add it for sells
                if position.premium is not None:
                    position_value -= position.premium * multiplier
                
                # Add weighted Greeks
                total_value += position_value
                total_delta += result.get("delta", 0) * multiplier
                total_gamma += result.get("gamma", 0) * multiplier
                total_theta += result.get("theta", 0) * multiplier
                total_vega += result.get("vega", 0) * multiplier
                total_rho += result.get("rho", 0) * multiplier
            
            # Add to price points
            price_points.append({
                "price": spot_price,
                "value": total_value,
                "delta": total_delta,
                "gamma": total_gamma,
                "theta": total_theta,
                "vega": total_vega,
                "rho": total_rho
            })
        
        # Return response
        return {
            "price_points": price_points,
            "current_price": current_price,
            "current_volatility": volatility
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in analyze_price_scenario: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error analyzing price scenario: {str(e)}")

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