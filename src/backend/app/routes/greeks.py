from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.models.database import get_db, DBPosition
from app.models.schemas import GreeksCalculationRequest, GreeksBase
from app.services.option_pricing import OptionPricer
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/greeks",
    tags=["greeks"],
    responses={404: {"description": "Not found"}},
)

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
        
        # Calculate Greeks
        result = option_pricer.price_option(
            option_type=position.option_type,
            strike=position.strike,
            expiration_date=position.expiration,
            spot_price=spot_price,
            volatility=volatility
        )
        
        return {
            "delta": result["delta"],
            "gamma": result["gamma"],
            "theta": result["theta"],
            "vega": result["vega"],
            "rho": result["rho"]
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
            
            # Add to totals
            total_delta += result["delta"] * sign * quantity
            total_gamma += result["gamma"] * sign * quantity
            total_theta += result["theta"] * sign * quantity
            total_vega += result["vega"] * sign * quantity
            total_rho += result["rho"] * sign * quantity
        
        return {
            "delta": total_delta,
            "gamma": total_gamma,
            "theta": total_theta,
            "vega": total_vega,
            "rho": total_rho
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio Greeks: {str(e)}") 