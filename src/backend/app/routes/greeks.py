from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.models.database import get_db, DBPosition
from app.models.schemas import GreeksCalculationRequest, GreeksBase
from typing import Dict, List, Optional, Literal
from app.services.option_pricing import OptionPricer
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/greeks",
    tags=["greeks"],
    responses={404: {"description": "Not found"}},
)

# Helper function to normalize Greek values to consistent scale
def _normalize_greek(value: float, greek_type: str = None) -> float:
    """Pass-through function that maintains Greek values.
    
    Greek values are now properly scaled at the source in option_pricing.py:
    - Delta: typically between -1.0 and 1.0
    - Gamma: typically between 0.0 and 0.2 for near ATM options
    - Theta: typically between -1.0 and 0.0 (negative for long options)
    - Vega: typically between 0.0 and 0.5 for ATM options
    - Rho: typically between -0.5 and 0.5
    
    These ranges are per single contract. Actual values will scale with position size.
    """
    # Handle null/None values
    if value is None:
        return 0.0
    
    # Values are already properly scaled in option_pricing.py
    return value

# Create dependency functions instead of direct instantiation
def get_option_pricer():
    """Dependency to get the option pricer service."""
    return OptionPricer()

def get_market_data_service():
    """Dependency to get the market data service."""
    return MarketDataService()


@router.post("/calculate", response_model=Dict[str, float])
def calculate_greeks(
    request: GreeksCalculationRequest,
    option_pricer: OptionPricer = Depends(get_option_pricer),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Calculate Greeks for an option contract.
    
    If spot_price is not provided, it will be fetched from market data.
    If volatility is not provided, a default value will be used.
    """
    try:
        # Get spot price if not provided
        spot_price = request.spot_price
        if spot_price is None:
            spot_price = market_data_service.get_stock_price(request.ticker)
        
        # Use provided volatility or default
        volatility = request.volatility or 0.3  # 30% default
        
        # Calculate Greeks
        result = option_pricer.price_option(
            option_type=request.option_type,
            strike=request.strike,
            expiration_date=request.expiration,
            spot_price=spot_price,
            volatility=volatility,
            risk_free_rate=request.risk_free_rate
        )
        
        # Adjust sign based on action (if provided) and quantity
        sign = -1 if request.action == "sell" else 1
        quantity = request.quantity if request.quantity is not None else 1
        
        # First normalize the raw Greeks values for consistent scale
        normalized_result = {
            "price": result["price"],  # Price is not affected by scaling
            "delta": _normalize_greek(result["delta"], "delta"),
            "gamma": _normalize_greek(result["gamma"], "gamma"),
            "theta": _normalize_greek(result["theta"], "theta"),
            "vega": _normalize_greek(result["vega"], "vega"),
            "rho": _normalize_greek(result["rho"], "rho"),
            "time_to_expiry": result["time_to_expiry"]
        }
        
        # Apply the adjustment to the Greeks based on action and quantity
        if request.action is not None:
            # Make sure quantity is positive - direction is handled by sign
            abs_quantity = abs(quantity)
            
            result = {
                "price": normalized_result["price"],  # Price is not affected by direction
                "delta": normalized_result["delta"] * sign * abs_quantity,
                "gamma": normalized_result["gamma"] * abs_quantity,  # Gamma doesn't change sign with position direction
                "theta": normalized_result["theta"] * sign * abs_quantity,
                "vega": normalized_result["vega"] * abs_quantity,  # Vega doesn't change sign with position direction
                "rho": normalized_result["rho"] * sign * abs_quantity,
                "time_to_expiry": normalized_result["time_to_expiry"]
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating Greeks: {str(e)}")


@router.post("/implied-volatility", response_model=Dict[str, float])
def calculate_implied_volatility(
    ticker: str,
    strike: float,
    expiration: str,
    option_type: str,
    option_price: float,
    american: bool = False,
    option_pricer: OptionPricer = Depends(get_option_pricer),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Calculate implied volatility from option price.
    """
    try:
        # Get spot price
        spot_price = market_data_service.get_stock_price(ticker)
        
        # Convert expiration string to datetime
        try:
            from datetime import datetime
            expiration_date = datetime.strptime(expiration, "%Y-%m-%d")
            print(f"Converted expiration string '{expiration}' to datetime: {expiration_date}")
        except ValueError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid date format for expiration. Expected YYYY-MM-DD, got: {expiration}. Error: {str(e)}"
            )
        
        # Calculate implied volatility
        implied_vol = option_pricer.calculate_implied_volatility(
            option_type=option_type,
            strike=strike,
            expiration_date=expiration_date,  # Now passing a datetime object
            spot_price=spot_price,
            option_price=option_price,
            american=american
        )
        
        return {"implied_volatility": implied_vol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating implied volatility: {str(e)}")


@router.get("/position/{position_id}", response_model=GreeksBase)
def get_position_greeks(
    position_id: str, 
    force_recalculate: bool = Query(False, description="Force recalculation of Greeks even if previously calculated"),
    db: Session = Depends(get_db),
    option_pricer: OptionPricer = Depends(get_option_pricer),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Calculate Greeks for an existing position.
    """
    # Get position from database
    position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    try:
        # Get spot price
        spot_price = market_data_service.get_stock_price(position.ticker)
        
        # Get implied volatility (or use default)
        volatility = market_data_service.get_implied_volatility(position.ticker)
        
        # Calculate fresh Greeks (not scaled by position)
        result = option_pricer.price_option(
            option_type=position.option_type,
            strike=position.strike,
            expiration_date=position.expiration,
            spot_price=spot_price,
            volatility=volatility
        )
        
        # First normalize the raw Greeks for consistent scale
        normalized_result = {
            "delta": _normalize_greek(result["delta"], "delta"),
            "gamma": _normalize_greek(result["gamma"], "gamma"),
            "theta": _normalize_greek(result["theta"], "theta"),
            "vega": _normalize_greek(result["vega"], "vega"),
            "rho": _normalize_greek(result["rho"], "rho")
        }
        
        # Adjust sign based on buy/sell
        sign = -1 if position.action == "sell" else 1
        quantity = abs(position.quantity)  # Ensure quantity is positive
        
        # Apply sign and quantity separately for proper scaling
        # Delta and rho flip sign for sell positions
        # Gamma, vega, and theta maintain their sign (they represent curvature and decay)
        return {
            "delta": normalized_result["delta"] * sign * quantity,
            # Gamma is always positive (measures curvature) but scales with quantity
            "gamma": normalized_result["gamma"] * quantity,
            # Theta is time decay - always negative for long options
            "theta": normalized_result["theta"] * sign * quantity,
            # Vega is volatility sensitivity - always positive but scales with position
            "vega": normalized_result["vega"] * quantity,
            "rho": normalized_result["rho"] * sign * quantity
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating Greeks: {str(e)}")


@router.get("/portfolio", response_model=GreeksBase)
def get_portfolio_greeks(
    position_ids: List[str] = Query(...),
    db: Session = Depends(get_db),
    option_pricer: OptionPricer = Depends(get_option_pricer),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Calculate aggregate Greeks for a portfolio of positions.
    """
    # Get positions from database
    positions = db.query(DBPosition).filter(DBPosition.id.in_(position_ids)).all()
    
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    
    # Initialize aggregate Greeks
    total_delta = 0.0
    total_gamma = 0.0
    total_theta = 0.0
    total_vega = 0.0
    total_rho = 0.0
    
    try:
        for position in positions:
            # Get spot price
            spot_price = market_data_service.get_stock_price(position.ticker)
            
            # Get implied volatility (or use default)
            volatility = market_data_service.get_implied_volatility(position.ticker)
            
            # Calculate Greeks
            result = option_pricer.price_option(
                option_type=position.option_type,
                strike=position.strike,
                expiration_date=position.expiration,
                spot_price=spot_price,
                volatility=volatility
            )
            
            # Adjust sign based on buy/sell and multiply by quantity
            sign = -1 if position.action == "sell" else 1
            quantity = position.quantity
            
            # First normalize the raw Greek values
            normalized_delta = _normalize_greek(result["delta"], "delta")
            normalized_gamma = _normalize_greek(result["gamma"], "gamma")
            normalized_theta = _normalize_greek(result["theta"], "theta")
            normalized_vega = _normalize_greek(result["vega"], "vega")
            normalized_rho = _normalize_greek(result["rho"], "rho")
            
            # Make sure quantity is positive - direction is handled by sign
            abs_quantity = abs(quantity)
            
            # Then add to totals with proper sign and quantity adjustments
            # Delta and rho flip sign for sell positions
            total_delta += normalized_delta * sign * abs_quantity
            # Gamma is always positive (measures curvature) but scales with quantity
            total_gamma += normalized_gamma * abs_quantity
            # Theta is time decay - always negative for long options
            total_theta += normalized_theta * sign * abs_quantity
            # Vega is volatility sensitivity - always positive but scales with position
            total_vega += normalized_vega * abs_quantity
            total_rho += normalized_rho * sign * abs_quantity
        
        # We don't normalize again, as values were already normalized per position
        # These are just summed up correctly with their signs and quantities
        return {
            "delta": total_delta,
            "gamma": total_gamma,
            "theta": total_theta,
            "vega": total_vega,
            "rho": total_rho
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio Greeks: {str(e)}") 