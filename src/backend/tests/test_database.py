import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, Position, OptionLeg
from app.models.schemas import PositionWithLegsCreate, OptionLegCreate


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestDatabaseOperations:
    """Test suite for database operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_expiration_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Sample position data
        self.position_data = PositionWithLegsCreate(
            name="AAPL Call Option",
            description="Test position",
            legs=[
                OptionLegCreate(
                    option_type="call",
                    strike=150.0,
                    expiration_date=self.sample_expiration_date,
                    quantity=1,
                    underlying_ticker="AAPL",
                    underlying_price=155.0,
                    option_price=5.75,
                    volatility=0.2
                )
            ]
        )

    def test_create_position(self, test_db):
        """Test creating a position in the database."""
        # Create a position
        position = Position(
            name=self.position_data.name,
            description=self.position_data.description
        )
        test_db.add(position)
        test_db.commit()
        test_db.refresh(position)
        
        # Verify the position was created
        assert position.id is not None
        assert position.name == "AAPL Call Option"
        assert position.description == "Test position"
        
        # Add option leg
        leg_data = self.position_data.legs[0]
        leg = OptionLeg(
            position_id=position.id,
            option_type=leg_data.option_type,
            strike=leg_data.strike,
            expiration_date=leg_data.expiration_date,
            quantity=leg_data.quantity,
            underlying_ticker=leg_data.underlying_ticker,
            underlying_price=leg_data.underlying_price,
            option_price=leg_data.option_price,
            volatility=leg_data.volatility
        )
        test_db.add(leg)
        test_db.commit()
        test_db.refresh(leg)
        
        # Verify the leg was created
        assert leg.id is not None
        assert leg.position_id == position.id
        assert leg.option_type == "call"
        assert leg.strike == 150.0
        assert leg.underlying_ticker == "AAPL"

    def test_retrieve_position(self, test_db):
        """Test retrieving a position from the database."""
        # Create a position with a leg
        position = Position(
            name=self.position_data.name,
            description=self.position_data.description
        )
        test_db.add(position)
        test_db.commit()
        test_db.refresh(position)
        
        leg_data = self.position_data.legs[0]
        leg = OptionLeg(
            position_id=position.id,
            option_type=leg_data.option_type,
            strike=leg_data.strike,
            expiration_date=leg_data.expiration_date,
            quantity=leg_data.quantity,
            underlying_ticker=leg_data.underlying_ticker,
            underlying_price=leg_data.underlying_price,
            option_price=leg_data.option_price,
            volatility=leg_data.volatility
        )
        test_db.add(leg)
        test_db.commit()
        
        # Retrieve the position
        retrieved_position = test_db.query(Position).filter(Position.id == position.id).first()
        
        # Verify the position was retrieved correctly
        assert retrieved_position is not None
        assert retrieved_position.id == position.id
        assert retrieved_position.name == "AAPL Call Option"
        
        # Retrieve the legs
        retrieved_legs = test_db.query(OptionLeg).filter(OptionLeg.position_id == position.id).all()
        
        # Verify the legs were retrieved correctly
        assert len(retrieved_legs) == 1
        assert retrieved_legs[0].option_type == "call"
        assert retrieved_legs[0].strike == 150.0
        assert retrieved_legs[0].underlying_ticker == "AAPL"

    def test_update_position(self, test_db):
        """Test updating a position in the database."""
        # Create a position
        position = Position(
            name=self.position_data.name,
            description=self.position_data.description
        )
        test_db.add(position)
        test_db.commit()
        test_db.refresh(position)
        
        # Update the position
        position.name = "Updated AAPL Position"
        position.description = "Updated description"
        test_db.commit()
        test_db.refresh(position)
        
        # Verify the position was updated
        assert position.name == "Updated AAPL Position"
        assert position.description == "Updated description"
        
        # Retrieve the position to double-check
        retrieved_position = test_db.query(Position).filter(Position.id == position.id).first()
        assert retrieved_position.name == "Updated AAPL Position"
        assert retrieved_position.description == "Updated description"

    def test_delete_position(self, test_db):
        """Test deleting a position from the database."""
        # Create a position
        position = Position(
            name=self.position_data.name,
            description=self.position_data.description
        )
        test_db.add(position)
        test_db.commit()
        test_db.refresh(position)
        
        # Add a leg
        leg_data = self.position_data.legs[0]
        leg = OptionLeg(
            position_id=position.id,
            option_type=leg_data.option_type,
            strike=leg_data.strike,
            expiration_date=leg_data.expiration_date,
            quantity=leg_data.quantity,
            underlying_ticker=leg_data.underlying_ticker,
            underlying_price=leg_data.underlying_price,
            option_price=leg_data.option_price,
            volatility=leg_data.volatility
        )
        test_db.add(leg)
        test_db.commit()
        
        # Delete the position
        test_db.delete(position)
        test_db.commit()
        
        # Verify the position was deleted
        retrieved_position = test_db.query(Position).filter(Position.id == position.id).first()
        assert retrieved_position is None
        
        # Verify the legs were also deleted (cascade)
        retrieved_legs = test_db.query(OptionLeg).filter(OptionLeg.position_id == position.id).all()
        assert len(retrieved_legs) == 0

    def test_position_with_multiple_legs(self, test_db):
        """Test creating a position with multiple option legs."""
        # Create a position
        position = Position(
            name="AAPL Straddle",
            description="Long straddle position"
        )
        test_db.add(position)
        test_db.commit()
        test_db.refresh(position)
        
        # Add call leg
        call_leg = OptionLeg(
            position_id=position.id,
            option_type="call",
            strike=150.0,
            expiration_date=self.sample_expiration_date,
            quantity=1,
            underlying_ticker="AAPL",
            underlying_price=150.0,
            option_price=5.75,
            volatility=0.2
        )
        test_db.add(call_leg)
        
        # Add put leg
        put_leg = OptionLeg(
            position_id=position.id,
            option_type="put",
            strike=150.0,
            expiration_date=self.sample_expiration_date,
            quantity=1,
            underlying_ticker="AAPL",
            underlying_price=150.0,
            option_price=5.25,
            volatility=0.2
        )
        test_db.add(put_leg)
        test_db.commit()
        
        # Retrieve the legs
        retrieved_legs = test_db.query(OptionLeg).filter(OptionLeg.position_id == position.id).all()
        
        # Verify both legs were created
        assert len(retrieved_legs) == 2
        
        # Verify the call leg
        call_legs = [leg for leg in retrieved_legs if leg.option_type == "call"]
        assert len(call_legs) == 1
        assert call_legs[0].strike == 150.0
        assert call_legs[0].option_price == 5.75
        
        # Verify the put leg
        put_legs = [leg for leg in retrieved_legs if leg.option_type == "put"]
        assert len(put_legs) == 1
        assert put_legs[0].strike == 150.0
        assert put_legs[0].option_price == 5.25

    def test_transaction_rollback(self, test_db):
        """Test transaction rollback on error."""
        # Start a transaction
        try:
            # Create a position
            position = Position(
                name=self.position_data.name,
                description=self.position_data.description
            )
            test_db.add(position)
            test_db.flush()  # Flush but don't commit
            
            # Try to add an invalid leg (missing required fields)
            invalid_leg = OptionLeg(
                position_id=position.id,
                # Missing required fields
            )
            test_db.add(invalid_leg)
            test_db.commit()  # This should fail
            
            # If we get here, the test failed
            assert False, "Transaction should have failed"
            
        except Exception:
            # Transaction should be rolled back
            test_db.rollback()
        
        # Verify no position was created
        positions = test_db.query(Position).all()
        assert len(positions) == 0

    def test_query_positions_by_ticker(self, test_db):
        """Test querying positions by underlying ticker."""
        # Create positions for different tickers
        aapl_position = Position(name="AAPL Call", description="Apple call option")
        test_db.add(aapl_position)
        test_db.commit()
        test_db.refresh(aapl_position)
        
        aapl_leg = OptionLeg(
            position_id=aapl_position.id,
            option_type="call",
            strike=150.0,
            expiration_date=self.sample_expiration_date,
            quantity=1,
            underlying_ticker="AAPL",
            underlying_price=155.0,
            option_price=5.75,
            volatility=0.2
        )
        test_db.add(aapl_leg)
        
        msft_position = Position(name="MSFT Call", description="Microsoft call option")
        test_db.add(msft_position)
        test_db.commit()
        test_db.refresh(msft_position)
        
        msft_leg = OptionLeg(
            position_id=msft_position.id,
            option_type="call",
            strike=250.0,
            expiration_date=self.sample_expiration_date,
            quantity=1,
            underlying_ticker="MSFT",
            underlying_price=255.0,
            option_price=6.25,
            volatility=0.18
        )
        test_db.add(msft_leg)
        test_db.commit()
        
        # Query positions with AAPL as underlying
        aapl_legs = test_db.query(OptionLeg).filter(OptionLeg.underlying_ticker == "AAPL").all()
        aapl_position_ids = [leg.position_id for leg in aapl_legs]
        aapl_positions = test_db.query(Position).filter(Position.id.in_(aapl_position_ids)).all()
        
        # Verify only AAPL positions are returned
        assert len(aapl_positions) == 1
        assert aapl_positions[0].name == "AAPL Call"
        
        # Query positions with MSFT as underlying
        msft_legs = test_db.query(OptionLeg).filter(OptionLeg.underlying_ticker == "MSFT").all()
        msft_position_ids = [leg.position_id for leg in msft_legs]
        msft_positions = test_db.query(Position).filter(Position.id.in_(msft_position_ids)).all()
        
        # Verify only MSFT positions are returned
        assert len(msft_positions) == 1
        assert msft_positions[0].name == "MSFT Call" 