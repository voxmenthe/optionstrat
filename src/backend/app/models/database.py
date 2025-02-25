from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import uuid

# SQLite database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./options.db"

# Create engine with check_same_thread=False for SQLite
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DBPosition(Base):
    """Database model for option positions."""
    __tablename__ = "positions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String, index=True)
    expiration = Column(DateTime)
    strike = Column(Float)
    option_type = Column(String)  # "call" or "put"
    action = Column(String)  # "buy" or "sell"
    quantity = Column(Integer)
    premium = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    """Dependency function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 