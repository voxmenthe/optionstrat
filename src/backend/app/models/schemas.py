from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal, Dict, List


class GreeksBase(BaseModel):
    """Base model for option Greeks."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class PositionBase(BaseModel):
    """Base model for option positions."""
    ticker: str
    expiration: datetime
    strike: float = Field(..., gt=0)
    option_type: Literal["call", "put"]
    action: Literal["buy", "sell"]
    quantity: int = Field(..., description="Positive for long positions, negative for short positions. Cannot be zero.")
    premium: Optional[float] = None


class PositionCreate(PositionBase):
    """Model for creating a new position."""
    pass


class PositionUpdate(BaseModel):
    """Model for updating an existing position."""
    ticker: Optional[str] = None
    expiration: Optional[datetime] = None
    strike: Optional[float] = Field(None, gt=0)
    option_type: Optional[Literal["call", "put"]] = None
    action: Optional[Literal["buy", "sell"]] = None
    quantity: Optional[int] = Field(None, description="Positive for long positions, negative for short positions. Cannot be zero.")
    premium: Optional[float] = None
    is_active: Optional[bool] = None


class Position(PositionBase):
    """Model for a position with additional fields."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    greeks: Optional[GreeksBase] = None

    class Config:
        orm_mode = True


class OptionLegCreate(BaseModel):
    """Model for creating a new option leg."""
    option_type: Literal["call", "put"]
    strike: float = Field(..., gt=0)
    expiration_date: str
    quantity: int = Field(..., description="Positive for long positions, negative for short positions. Cannot be zero.")
    underlying_ticker: str
    underlying_price: float
    option_price: float
    volatility: float


class OptionLegUpdate(BaseModel):
    """Model for updating an option leg."""
    option_type: Optional[Literal["call", "put"]] = None
    strike: Optional[float] = Field(None, gt=0)
    expiration_date: Optional[str] = None
    quantity: Optional[int] = None
    underlying_ticker: Optional[str] = None
    underlying_price: Optional[float] = None
    option_price: Optional[float] = None
    volatility: Optional[float] = None


class OptionLeg(OptionLegCreate):
    """Model for an option leg with additional fields."""
    id: str
    position_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PositionWithLegsCreate(BaseModel):
    """Model for creating a new position with multiple legs."""
    name: str
    description: Optional[str] = None
    legs: List[OptionLegCreate]


class PositionWithLegs(BaseModel):
    """Model for a position with its option legs."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    legs: List[OptionLeg]

    class Config:
        orm_mode = True


class GreeksCalculationRequest(BaseModel):
    """Model for requesting Greeks calculation."""
    ticker: str
    expiration: datetime
    strike: float
    option_type: Literal["call", "put"]
    spot_price: Optional[float] = None
    volatility: Optional[float] = None
    risk_free_rate: Optional[float] = 0.05
    action: Optional[Literal["buy", "sell"]] = None
    quantity: Optional[int] = None


class ScenarioAnalysisRequest(BaseModel):
    """Model for requesting scenario analysis."""
    position_ids: List[str]
    price_range: Optional[Dict[str, float]] = None  # {"min": float, "max": float, "steps": int}
    volatility_range: Optional[Dict[str, float]] = None  # {"min": float, "max": float, "steps": int}
    days_to_expiry_range: Optional[Dict[str, int]] = None  # {"min": int, "max": int, "steps": int}


class MarketDataRequest(BaseModel):
    """Model for requesting market data."""
    ticker: str
    date: Optional[datetime] = None 


class PnLResult(BaseModel):
    """Model for P&L calculation results."""
    position_id: str
    pnl_amount: float
    pnl_percent: float
    initial_value: float
    current_value: float
    implied_volatility: Optional[float] = None
    underlying_price: Optional[float] = None
    calculation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    days_forward: Optional[int] = None
    price_change_percent: Optional[float] = None


class PnLCalculationParams(BaseModel):
    """Model for P&L calculation parameters."""
    days_forward: Optional[int] = 0
    price_change_percent: Optional[float] = 0.0


class BulkPnLCalculationRequest(BaseModel):
    """Model for requesting bulk P&L calculations."""
    position_ids: List[str]
    days_forward: Optional[int] = 0
    price_change_percent: Optional[float] = 0.0