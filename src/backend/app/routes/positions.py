from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from app.models.database import get_db, DBPosition, Position, OptionLeg
from app.models.schemas import Position as PositionSchema, PositionCreate, PositionUpdate, PositionWithLegsCreate, PositionWithLegs
from app.services.option_pricing import OptionPricer
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/positions",
    tags=["positions"],
    responses={404: {"description": "Not found"}},
)

# Create dependency functions instead of direct instantiation
def get_option_pricer():
    """Dependency to get the option pricer service."""
    return OptionPricer()

def get_market_data_service():
    """Dependency to get the market data service."""
    return MarketDataService()


@router.post("/", response_model=PositionSchema)
def create_position(position: PositionCreate, db: Session = Depends(get_db)):
    """
    Create a new option position.
    """
    db_position = DBPosition(
        id=str(uuid.uuid4()),
        ticker=position.ticker,
        expiration=position.expiration,
        strike=position.strike,
        option_type=position.option_type,
        action=position.action,
        quantity=position.quantity,
        premium=position.premium,
        is_active=True
    )
    
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    
    return db_position


@router.post("/with-legs", response_model=PositionWithLegs, status_code=201)
def create_position_with_legs(position: PositionWithLegsCreate, db: Session = Depends(get_db)):
    """
    Create a new position with multiple option legs.
    """
    # Create the position
    db_position = Position(
        id=str(uuid.uuid4()),
        name=position.name,
        description=position.description
    )
    
    db.add(db_position)
    db.flush()  # Flush to get the ID without committing
    
    # Create the legs
    for leg_data in position.legs:
        db_leg = OptionLeg(
            id=str(uuid.uuid4()),
            position_id=db_position.id,
            option_type=leg_data.option_type,
            strike=leg_data.strike,
            expiration_date=leg_data.expiration_date,
            quantity=leg_data.quantity,
            underlying_ticker=leg_data.underlying_ticker,
            underlying_price=leg_data.underlying_price,
            option_price=leg_data.option_price,
            volatility=leg_data.volatility
        )
        db.add(db_leg)
    
    # Commit all changes
    db.commit()
    db.refresh(db_position)
    
    # Return the position with legs
    return db_position


@router.get("/", response_model=List[PositionSchema])
def read_positions(
    skip: int = 0, 
    limit: int = 100, 
    active_only: bool = True,
    ticker: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all positions with optional filtering.
    """
    query = db.query(DBPosition)
    
    if active_only:
        query = query.filter(DBPosition.is_active == True)
    
    if ticker:
        query = query.filter(DBPosition.ticker == ticker)
    
    positions = query.offset(skip).limit(limit).all()
    
    # Add Greeks to each position
    for position in positions:
        try:
            # Try to get current price from market data service
            spot_price = get_market_data_service().get_stock_price(position.ticker)
            
            # Calculate Greeks
            greeks = get_option_pricer().price_option(
                option_type=position.option_type,
                strike=position.strike,
                expiration_date=position.expiration,
                spot_price=spot_price,
                volatility=0.3  # Default volatility
            )
            
            # Add Greeks to position
            position.greeks = {
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
                "rho": greeks["rho"]
            }
        except Exception as e:
            # If market data or Greeks calculation fails, continue without Greeks
            print(f"Error calculating Greeks for position {position.id}: {e}")
            position.greeks = None
    
    return positions


@router.get("/{position_id}", response_model=PositionSchema)
def read_position(position_id: str, db: Session = Depends(get_db)):
    """
    Get a specific position by ID.
    """
    position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    try:
        # Try to get current price from market data service
        spot_price = get_market_data_service().get_stock_price(position.ticker)
        
        # Calculate Greeks
        greeks = get_option_pricer().price_option(
            option_type=position.option_type,
            strike=position.strike,
            expiration_date=position.expiration,
            spot_price=spot_price,
            volatility=0.3  # Default volatility
        )
        
        # Add Greeks to position
        position.greeks = {
            "delta": greeks["delta"],
            "gamma": greeks["gamma"],
            "theta": greeks["theta"],
            "vega": greeks["vega"],
            "rho": greeks["rho"]
        }
    except Exception as e:
        # If market data or Greeks calculation fails, continue without Greeks
        print(f"Error calculating Greeks for position {position.id}: {e}")
        position.greeks = None
    
    return position


@router.put("/{position_id}", response_model=PositionSchema)
def update_position(
    position_id: str, 
    position_update: PositionUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a position.
    """
    db_position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Update fields if provided
    update_data = position_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_position, key, value)
    
    # Update the updated_at timestamp
    db_position.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_position)
    
    return db_position


@router.delete("/{position_id}", response_model=PositionSchema)
def delete_position(position_id: str, db: Session = Depends(get_db)):
    """
    Delete a position (soft delete by setting is_active to False).
    """
    db_position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Soft delete
    db_position.is_active = False
    db_position.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_position)
    
    return db_position 