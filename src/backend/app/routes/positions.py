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
    # Validate quantity - it can't be zero, but can be negative for short positions
    if position.quantity == 0:
        raise HTTPException(status_code=422, detail="Quantity cannot be zero")
    
    # Ensure consistency between action and quantity sign
    action = position.action
    quantity = position.quantity
    
    # If action is 'sell' but quantity is positive, make quantity negative
    if action == 'sell' and quantity > 0:
        quantity = -abs(quantity)
    
    # If quantity is negative but action is 'buy', change action to 'sell'
    if quantity < 0 and action == 'buy':
        action = 'sell'
        quantity = -abs(quantity)  # Ensure quantity is negative
    
    db_position = DBPosition(
        id=str(uuid.uuid4()),
        ticker=position.ticker,
        expiration=position.expiration,
        strike=position.strike,
        option_type=position.option_type,
        action=action,
        quantity=quantity,
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
    # Validate all leg quantities - they can't be zero
    for i, leg in enumerate(position.legs):
        if leg.quantity == 0:
            raise HTTPException(status_code=422, detail=f"Quantity for leg {i+1} cannot be zero")
    
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
        # For option legs, ensure consistency of quantity
        # Since OptionLeg doesn't have an 'action' field like DBPosition does,
        # we'll just ensure that negative quantities represent short positions
        quantity = leg_data.quantity
        
        # Store the adjusted leg
        db_leg = OptionLeg(
            id=str(uuid.uuid4()),
            position_id=db_position.id,
            option_type=leg_data.option_type,
            strike=leg_data.strike,
            expiration_date=leg_data.expiration_date,
            quantity=quantity,
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
    
    # Check if we need to ensure consistency between action and quantity
    need_quantity_action_sync = False
    new_action = update_data.get('action', db_position.action)
    new_quantity = update_data.get('quantity', db_position.quantity)
    
    # If we're updating just one of action or quantity, we may need to sync them
    if ('action' in update_data and 'quantity' not in update_data) or \
       ('quantity' in update_data and 'action' not in update_data):
        need_quantity_action_sync = True
    
    # Apply all updates
    for key, value in update_data.items():
        setattr(db_position, key, value)
    
    # Ensure consistency between action and quantity
    if need_quantity_action_sync:
        # If action is 'sell' but quantity is positive, make quantity negative
        if db_position.action == 'sell' and db_position.quantity > 0:
            db_position.quantity = -abs(db_position.quantity)
        
        # If quantity is negative but action is 'buy', change action to 'sell'
        if db_position.quantity < 0 and db_position.action == 'buy':
            db_position.action = 'sell'
    
    # Update the updated_at timestamp
    db_position.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_position)
    
    return db_position


@router.put("/with-legs/{position_id}", response_model=PositionWithLegs)
def update_position_with_legs(
    position_id: str, 
    position_update: dict, 
    db: Session = Depends(get_db)
):
    """
    Update a position with legs.
    """
    # Find the position with the given ID
    db_position = db.query(Position).filter(Position.id == position_id).first()
    
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Update the basic position fields
    if "name" in position_update:
        db_position.name = position_update["name"]
    if "description" in position_update:
        db_position.description = position_update["description"]
    
    # If legs are provided, update them
    if "legs" in position_update and isinstance(position_update["legs"], list):
        # Loop through each leg update
        for leg_update in position_update["legs"]:
            if "id" in leg_update:
                # Find the existing leg
                leg = db.query(OptionLeg).filter(OptionLeg.id == leg_update["id"]).first()
                if leg:
                    # Update the existing leg
                    for key, value in leg_update.items():
                        if key != "id":
                            setattr(leg, key, value)
                    
                    # Ensure quantity is properly signed (no action field exists in OptionLeg)
                    # Negative quantity implies a short position
            else:
                # This is a new leg, add it to the position
                quantity = leg_update.get("quantity", 0)
                
                new_leg = OptionLeg(
                    id=str(uuid.uuid4()),
                    position_id=db_position.id,
                    option_type=leg_update.get("option_type"),
                    strike=leg_update.get("strike"),
                    expiration_date=leg_update.get("expiration_date"),
                    quantity=quantity,
                    underlying_ticker=leg_update.get("underlying_ticker"),
                    underlying_price=leg_update.get("underlying_price"),
                    option_price=leg_update.get("option_price"),
                    volatility=leg_update.get("volatility")
                )
                db.add(new_leg)
    
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


@router.get("/with-legs/", response_model=List[PositionWithLegs])
def read_positions_with_legs(
    skip: int = 0, 
    limit: int = 100,
    strategy_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all positions with legs with optional filtering.
    """
    query = db.query(Position)
    
    # Apply filters if provided
    if strategy_type:
        # Case-insensitive search on name - convert both sides to lower case for comparison
        # SQLite specific function for case-insensitive comparison
        query = query.filter(Position.name.ilike(f'%{strategy_type}%'))
    
    positions = query.offset(skip).limit(limit).all()
    return positions


@router.get("/with-legs/{position_id}", response_model=PositionWithLegs)
def read_position_with_legs(position_id: str, db: Session = Depends(get_db)):
    """
    Get a specific position with legs by ID.
    """
    position = db.query(Position).filter(Position.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    return position


@router.delete("/with-legs/{position_id}")
def delete_position_with_legs(position_id: str, db: Session = Depends(get_db)):
    """
    Delete a position with legs.
    """
    position = db.query(Position).filter(Position.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Hard delete the position and all its legs (cascade delete)
    db.delete(position)
    db.commit()
    
    return {"detail": "Position deleted"} 