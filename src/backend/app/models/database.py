from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime
from pathlib import Path
import uuid

# SQLite database URL (anchored to backend root)
BASE_DIR = Path(__file__).resolve().parents[2]
OPTIONS_DB_PATH = BASE_DIR / "options.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{OPTIONS_DB_PATH}"

# Create engine with check_same_thread=False for SQLite
# Set pool_size to 20 and max_overflow to 30 to handle more concurrent connections
# Set pool_recycle to 3600 (1 hour) to prevent stale connections
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # Verify connections before using them
    pool_timeout=60      # Increase timeout to 60 seconds
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Position(Base):
    """Database model for option positions/strategies."""
    __tablename__ = "positions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    
    # Relationship with option legs
    legs = relationship("OptionLeg", back_populates="position", cascade="all, delete-orphan")


class OptionLeg(Base):
    """Database model for individual option legs within a position."""
    __tablename__ = "option_legs"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    position_id = Column(String, ForeignKey("positions.id", ondelete="CASCADE"))
    option_type = Column(String)  # "call" or "put"
    strike = Column(Float)
    expiration_date = Column(String)
    quantity = Column(Integer)
    underlying_ticker = Column(String, index=True)
    underlying_price = Column(Float)
    option_price = Column(Float)
    volatility = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    
    # Relationship with position
    position = relationship("Position", back_populates="legs")


# Keep the DBPosition class for backward compatibility if needed
class DBPosition(Base):
    """Database model for option positions (legacy)."""
    __tablename__ = "db_positions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String, index=True)
    expiration = Column(DateTime)
    strike = Column(Float)
    option_type = Column(String)  # "call" or "put"
    action = Column(String)  # "buy" or "sell"
    quantity = Column(Integer)
    premium = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))


class CacheEntry(Base):
    """Database model for caching when Redis is unavailable."""
    __tablename__ = "cache_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)  # Stores JSON serialized data
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))


class PositionPnLResult(Base):
    """Database model for position P&L calculation results."""
    __tablename__ = "position_pnl_results"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    position_id = Column(String, index=True)
    pnl_amount = Column(Float)
    pnl_percent = Column(Float)
    initial_value = Column(Float)
    current_value = Column(Float)
    implied_volatility = Column(Float, nullable=True)
    historical_volatility = Column(Float, nullable=True)  # Store the historical volatility calculation
    underlying_price = Column(Float, nullable=True)
    calculation_timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    is_theoretical = Column(Boolean, default=False)  # Whether this is a theoretical or actual P&L
    days_forward = Column(Integer, nullable=True)     # For theoretical P&L
    price_change_percent = Column(Float, nullable=True)  # For theoretical P&L
    volatility_days = Column(Integer, nullable=True)  # Number of days used for volatility calculation
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))




# Create tables
# Only remove the database file if it doesn't exist yet, otherwise we'd lose existing data
if not OPTIONS_DB_PATH.exists():
    # Create all tables
    Base.metadata.create_all(bind=engine)
else:
    # Just make sure the schema is up to date without recreating the entire database
    # This allows adding new tables/columns without losing data
    Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    """Dependency function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
