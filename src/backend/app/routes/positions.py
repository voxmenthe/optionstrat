from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from app.models.database import get_db, DBPosition
from app.models.schemas import Position, PositionCreate, PositionUpdate
from app.services.option_pricing import OptionPricer
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/positions",
    tags=["positions"],
    responses={404: {"description": "Not found"}},
)

option_pricer = OptionPricer()
market_data_service = MarketDataService()


@router.post("/", response_model=Position)
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


@router.get("/", response_model=List[Position])
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
            spot_price = market_data_service.get_stock_price(position.ticker)
            
            # Calculate Greeks
            greeks = option_pricer.price_option(
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


@router.get("/{position_id}", response_model=Position)
def read_position(position_id: str, db: Session = Depends(get_db)):
    """
    Get a specific position by ID.
    """
    position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    try:
        # Try to get current price from market data service
        spot_price = market_data_service.get_stock_price(position.ticker)
        
        # Calculate Greeks
        greeks = option_pricer.price_option(
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


@router.put("/{position_id}", response_model=Position)
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


@router.delete("/{position_id}", response_model=Position)
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