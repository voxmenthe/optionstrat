from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timedelta
import math

from app.models.database import get_db, DBPosition, Position, OptionLeg, PositionPnLResult
from app.models.schemas import Position as PositionSchema, PositionCreate, PositionUpdate, PositionWithLegsCreate, PositionWithLegs
from app.models.schemas import PnLResult, PnLCalculationParams, BulkPnLCalculationRequest
from app.services.option_pricing import OptionPricer
from app.services.market_data import MarketDataService
from app.services.scenario_engine import ScenarioEngine

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

def get_scenario_engine():
    """Dependency to get the scenario engine service."""
    return ScenarioEngine()


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


@router.get("/{position_id}/pnl", response_model=PnLResult)
def calculate_position_pnl(
    position_id: str, 
    recalculate: bool = Query(False, description="Force recalculation instead of using saved values"),
    db: Session = Depends(get_db), 
    market_data_service = Depends(get_market_data_service)
):
    """
    Calculate current profit and loss for a specific position.
    If recalculate is False, will attempt to use previously saved values.
    """
    # Check if we have a saved result and recalculation is not requested
    if not recalculate:
        saved_result = db.query(PositionPnLResult).filter(
            PositionPnLResult.position_id == position_id,
            PositionPnLResult.is_theoretical == False
        ).order_by(PositionPnLResult.calculation_timestamp.desc()).first()
        
        if saved_result:
            # Return saved result - include all fields from the database
            result = PnLResult(
                position_id=saved_result.position_id,
                pnl_amount=saved_result.pnl_amount,
                pnl_percent=saved_result.pnl_percent,
                initial_value=saved_result.initial_value,
                current_value=saved_result.current_value,
                implied_volatility=saved_result.implied_volatility,
                underlying_price=saved_result.underlying_price,
                calculation_timestamp=saved_result.calculation_timestamp,
                days_forward=saved_result.days_forward,
                price_change_percent=saved_result.price_change_percent
            )
            print(f"Using cached PnL result for position {position_id} from {saved_result.calculation_timestamp}")
            return result
    
    # Get the position
    position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Get the current market price for the underlying
    try:
        current_spot_price = market_data_service.get_stock_price(position.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Calculate initial value (what was paid for the position)
    initial_value = 0
    if position.premium is not None:
        initial_value = abs(position.premium * position.quantity * 100)  # Convert to dollar amount (100 shares per contract)
        # Calculate current option value with implied volatility
    option_pricer = get_option_pricer()
    try:
        # Get current implied volatility or use default
        implied_volatility = 0.3  # Default volatility
        
        # Try to estimate implied volatility if we have enough market data
        try:
            # This is a simplified approach - in reality you'd use a more sophisticated IV calculation
            if position.premium is not None and position.premium > 0:
                iv_result = option_pricer.calculate_implied_volatility(
                    option_type=position.option_type,
                    strike=position.strike,
                    expiration_date=position.expiration,
                    spot_price=current_spot_price,
                    option_price=position.premium
                )
                if iv_result and "implied_volatility" in iv_result:
                    implied_volatility = iv_result["implied_volatility"]
        except Exception as e:
            print(f"Could not calculate implied volatility: {str(e)}")
            # Continue with default volatility
        
        # Calculate the current option price
        price_result = option_pricer.price_option(
            option_type=position.option_type,
            strike=position.strike,
            expiration_date=position.expiration,
            spot_price=current_spot_price,
            volatility=implied_volatility
        )
        current_option_price = price_result["price"]
        
        # Current value of the position
        current_value = current_option_price * abs(position.quantity) * 100  # 100 shares per contract
        
        # Calculate P&L
        if position.action == "buy":
            pnl_amount = current_value - initial_value
        else:  # sell/short position
            pnl_amount = initial_value - current_value
        
        # Calculate P&L percentage
        pnl_percent = 0
        if initial_value > 0:
            pnl_percent = (pnl_amount / initial_value) * 100
        
        # Create PnL result object
        pnl_result = PnLResult(
            position_id=position_id,
            pnl_amount=pnl_amount,
            pnl_percent=pnl_percent,
            initial_value=initial_value,
            current_value=current_value,
            implied_volatility=implied_volatility,
            underlying_price=current_spot_price,
            calculation_timestamp=datetime.utcnow()
        )
        
        # Save to database for persistence
        try:
            # Wrap in transaction to ensure atomicity
            # First delete any existing results for this position
            db.query(PositionPnLResult).filter(
                PositionPnLResult.position_id == position_id,
                PositionPnLResult.is_theoretical == False
            ).delete()
            
            # Then save the new result
            db_pnl_result = PositionPnLResult(
                position_id=position_id,
                pnl_amount=pnl_amount,
                pnl_percent=pnl_percent,
                initial_value=initial_value,
                current_value=current_value,
                implied_volatility=implied_volatility,
                underlying_price=current_spot_price,
                calculation_timestamp=datetime.utcnow(),
                is_theoretical=False
            )
            db.add(db_pnl_result)
            db.commit()
            print(f"Successfully saved PnL result for position {position_id} with ID {db_pnl_result.id}")
        except Exception as e:
            db.rollback()
            print(f"Error saving PnL result to database: {str(e)}")
            # We'll still return the result even if saving fails
        
        return pnl_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating P&L: {str(e)}")


@router.post("/{position_id}/theoretical-pnl", response_model=PnLResult)
def calculate_theoretical_position_pnl(
    position_id: str, 
    params: PnLCalculationParams, 
    recalculate: bool = Query(False, description="Force recalculation instead of using saved values"),
    db: Session = Depends(get_db),
    market_data_service = Depends(get_market_data_service),
    option_pricer = Depends(get_option_pricer)
):
    """
    Calculate theoretical profit and loss for a specific position based on days forward and price change percentage.
    If recalculate is False, will attempt to use previously saved values.
    """
    # Check if we have a saved result with the same parameters and recalculation is not requested
    if not recalculate:
        saved_result = db.query(PositionPnLResult).filter(
            PositionPnLResult.position_id == position_id,
            PositionPnLResult.is_theoretical == True,
            PositionPnLResult.days_forward == params.days_forward,
            PositionPnLResult.price_change_percent == params.price_change_percent
        ).order_by(PositionPnLResult.calculation_timestamp.desc()).first()
        
        if saved_result:
            # Return saved result - include all fields from the database
            result = PnLResult(
                position_id=saved_result.position_id,
                pnl_amount=saved_result.pnl_amount,
                pnl_percent=saved_result.pnl_percent,
                initial_value=saved_result.initial_value,
                current_value=saved_result.current_value,
                implied_volatility=saved_result.implied_volatility,
                underlying_price=saved_result.underlying_price,
                calculation_timestamp=saved_result.calculation_timestamp,
                days_forward=saved_result.days_forward,
                price_change_percent=saved_result.price_change_percent
            )
            print(f"Using cached theoretical PnL result for position {position_id} with days_forward={params.days_forward}, price_change={params.price_change_percent}")
            return result
    
    # Get the position
    position = db.query(DBPosition).filter(DBPosition.id == position_id).first()
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Get the current market price for the underlying
    try:
        current_spot_price = market_data_service.get_stock_price(position.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")
    
    # Calculate the projected spot price
    projected_spot_price = current_spot_price * (1 + params.price_change_percent / 100)
    
    # Calculate initial value (what was paid for the position)
    initial_value = 0
    if position.premium is not None:
        initial_value = abs(position.premium * position.quantity * 100)  # Convert to dollar amount (100 shares per contract)
    
    # Calculate the projected expiration date
    original_expiry = position.expiration
    days_to_expiry = (original_expiry - datetime.now()).days
    projected_days_to_expiry = max(0, days_to_expiry - params.days_forward)
    projected_expiry = datetime.now() + timedelta(days=projected_days_to_expiry)
    
    try:
        # Get current implied volatility or use default
        implied_volatility = 0.3  # Default volatility
        
        # Try to estimate implied volatility if we have enough market data
        try:
            # This is a simplified approach - in reality you'd use a more sophisticated IV calculation
            if position.premium is not None and position.premium > 0:
                iv_result = option_pricer.calculate_implied_volatility(
                    option_type=position.option_type,
                    strike=position.strike,
                    expiration_date=position.expiration,
                    spot_price=current_spot_price,
                    option_price=position.premium
                )
                if iv_result and "implied_volatility" in iv_result:
                    implied_volatility = iv_result["implied_volatility"]
        except Exception as e:
            print(f"Could not calculate implied volatility: {str(e)}")
            # Continue with default volatility
        
        # Calculate theoretical option price
        price_result = option_pricer.price_option(
            option_type=position.option_type,
            strike=position.strike,
            expiration_date=projected_expiry,
            spot_price=projected_spot_price,
            volatility=implied_volatility
        )
        theoretical_option_price = price_result["price"]
        
        # Theoretical value of the position
        theoretical_value = theoretical_option_price * abs(position.quantity) * 100  # 100 shares per contract
        
        # Calculate P&L
        if position.action == "buy":
            pnl_amount = theoretical_value - initial_value
        else:  # sell/short position
            pnl_amount = initial_value - theoretical_value
        
        # Calculate P&L percentage
        pnl_percent = 0
        if initial_value > 0:
            pnl_percent = (pnl_amount / initial_value) * 100
        
        # Create result object
        pnl_result = PnLResult(
            position_id=position_id,
            pnl_amount=pnl_amount,
            pnl_percent=pnl_percent,
            initial_value=initial_value,
            current_value=theoretical_value,
            implied_volatility=implied_volatility,
            underlying_price=projected_spot_price,
            calculation_timestamp=datetime.utcnow(),
            days_forward=params.days_forward,
            price_change_percent=params.price_change_percent
        )
        
        # Save to database for persistence
        try:
            # Wrap in transaction to ensure atomicity
            # First delete any existing theoretical results with same parameters
            db.query(PositionPnLResult).filter(
                PositionPnLResult.position_id == position_id,
                PositionPnLResult.is_theoretical == True,
                PositionPnLResult.days_forward == params.days_forward,
                PositionPnLResult.price_change_percent == params.price_change_percent
            ).delete()
            
            # Then save the new result
            db_pnl_result = PositionPnLResult(
                position_id=position_id,
                pnl_amount=pnl_amount,
                pnl_percent=pnl_percent,
                initial_value=initial_value,
                current_value=theoretical_value,
                implied_volatility=implied_volatility,
                underlying_price=projected_spot_price,
                calculation_timestamp=datetime.utcnow(),
                is_theoretical=True,
                days_forward=params.days_forward,
                price_change_percent=params.price_change_percent
            )
            db.add(db_pnl_result)
            db.commit()
            print(f"Successfully saved theoretical PnL result for position {position_id} with ID {db_pnl_result.id}")
        except Exception as e:
            db.rollback()
            print(f"Error saving theoretical PnL result to database: {str(e)}")
            # We'll still return the result even if saving fails
        
        return pnl_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating theoretical P&L: {str(e)}")


@router.post("/bulk-theoretical-pnl", response_model=List[PnLResult])
def calculate_bulk_theoretical_pnl(
    request: BulkPnLCalculationRequest,
    db: Session = Depends(get_db),
    market_data_service = Depends(get_market_data_service),
    option_pricer = Depends(get_option_pricer)
):
    """
    Calculate theoretical profit and loss for multiple positions based on days forward and price change percentage.
    """
    results = []
    
    # Create PnL calculation params
    params = PnLCalculationParams(
        days_forward=request.days_forward,
        price_change_percent=request.price_change_percent
    )
    
    # Process each position
    for position_id in request.position_ids:
        try:
            # Use the single position theoretical P&L endpoint
            result = calculate_theoretical_position_pnl(
                position_id=position_id,
                params=params,
                db=db,
                market_data_service=market_data_service,
                option_pricer=option_pricer
            )
            results.append(result)
        except HTTPException as e:
            # Skip positions that weren't found or had calculation errors
            print(f"Error calculating theoretical P&L for position {position_id}: {e.detail}")
        except Exception as e:
            print(f"Unexpected error for position {position_id}: {str(e)}")
    
    return results