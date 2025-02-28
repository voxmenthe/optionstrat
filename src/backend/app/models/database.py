from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import uuid
import os

# SQLite database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./options.db"

# Create engine with check_same_thread=False for SQLite
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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


# Create tables
# Check if the database file exists and remove it if it does (for testing purposes)
if os.path.exists("./options.db"):
    os.remove("./options.db")

# Create all tables
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    """Dependency function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 