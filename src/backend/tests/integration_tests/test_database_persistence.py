"""
Integration test for database persistence and retrieval.

This test verifies the database operations and relationships between entities.
"""
import pytest
from datetime import datetime, timedelta
import uuid

from app.models.database import Position, OptionLeg


class TestDatabasePersistence:
    """Integration tests for database persistence and retrieval."""
    
    def setup_method(self):
        """Set up test data."""
        self.today = datetime.today().date()
        self.expiry_date = self.today + timedelta(days=30)
        self.expiry_str = self.expiry_date.strftime("%Y-%m-%d")
        
        self.position_data = {
            "name": "Test Iron Condor",
            "ticker": "SPY",
            "strategy_type": "IRON_CONDOR",
            "description": "A test position with all four legs of an iron condor"
        }
        
        self.legs_data = [
            {
                "option_type": "call",
                "strike": 420,
                "expiration_date": self.expiry_str,
                "quantity": 1,  # LONG position
                "underlying_ticker": "SPY",
                "underlying_price": 400.0,
                "option_price": 5.2,
                "volatility": 0.18
            },
            {
                "option_type": "call",
                "strike": 430,
                "expiration_date": self.expiry_str,
                "quantity": -1,  # SHORT position
                "underlying_ticker": "SPY",
                "underlying_price": 400.0,
                "option_price": 2.1,
                "volatility": 0.22
            },
            {
                "option_type": "put",
                "strike": 380,
                "expiration_date": self.expiry_str,
                "quantity": -1,  # SHORT position
                "underlying_ticker": "SPY",
                "underlying_price": 400.0,
                "option_price": 4.8,
                "volatility": 0.20
            },
            {
                "option_type": "put",
                "strike": 370,
                "expiration_date": self.expiry_str,
                "quantity": 1,  # LONG position
                "underlying_ticker": "SPY",
                "underlying_price": 400.0,
                "option_price": 1.9,
                "volatility": 0.24
            }
        ]
    
    def test_position_creation_with_legs(self, db_session):
        """Test creating a position with multiple legs in the database."""
        # Create position object
        position = Position(
            id=str(uuid.uuid4()),
            name=self.position_data["name"],
            description=self.position_data["description"]
        )
        
        # Create and associate legs
        for leg_data in self.legs_data:
            leg = OptionLeg(
                id=str(uuid.uuid4()),
                option_type=leg_data["option_type"],
                strike=leg_data["strike"],
                expiration_date=leg_data["expiration_date"],
                quantity=leg_data["quantity"],
                underlying_ticker=leg_data["underlying_ticker"],
                underlying_price=leg_data["underlying_price"],
                option_price=leg_data["option_price"],
                volatility=leg_data["volatility"]
            )
            position.legs.append(leg)
        
        # Add to database and commit
        db_session.add(position)
        db_session.commit()
        
        # Get the position ID for later retrieval
        position_id = position.id
        
        # Clear the session to ensure we're testing retrieval
        db_session.expunge_all()
        
        # Retrieve the position and verify
        retrieved_position = db_session.query(Position).filter_by(id=position_id).first()
        assert retrieved_position is not None
        assert retrieved_position.name == self.position_data["name"]
        assert retrieved_position.description == self.position_data["description"]
        
        # Verify the legs were saved with relationships intact
        assert len(retrieved_position.legs) == 4
        
        # Verify each leg has the correct properties
        for i, original_leg in enumerate(self.legs_data):
            db_leg = next((leg for leg in retrieved_position.legs if leg.strike == original_leg["strike"] and leg.option_type == original_leg["option_type"]), None)
            assert db_leg is not None
            assert db_leg.option_price == original_leg["option_price"]
            assert db_leg.volatility == original_leg["volatility"]
            assert db_leg.underlying_ticker == original_leg["underlying_ticker"]
            assert db_leg.quantity == original_leg["quantity"]
        
        # Test updating the position
        retrieved_position.name = "Updated Iron Condor"
        db_session.commit()
        
        # Clear session again
        db_session.expunge_all()
        
        # Retrieve again and verify update
        updated_position = db_session.query(Position).filter_by(id=position_id).first()
        assert updated_position.name == "Updated Iron Condor"
        
        # Test deleting a leg
        leg_to_delete = updated_position.legs[0]
        db_session.delete(leg_to_delete)
        db_session.commit()
        
        # Clear session again
        db_session.expunge_all()
        
        # Verify leg was deleted
        final_position = db_session.query(Position).filter_by(id=position_id).first()
        assert len(final_position.legs) == 3
        
        # Test cascade delete
        db_session.delete(final_position)
        db_session.commit()
        
        # Verify position and all legs are gone
        deleted_position = db_session.query(Position).filter_by(id=position_id).first()
        assert deleted_position is None
        
        leg_count = db_session.query(OptionLeg).filter_by(position_id=position_id).count()
        assert leg_count == 0
    
    def test_position_api_persistence(self, integration_client, db_session):
        """Test database persistence through the API."""
        # First, create a position via API
        api_position = {
            "name": self.position_data["name"],
            "description": self.position_data["description"],
            "legs": [
                # Create a copy of each leg with positive quantities
                # The OptionLegCreate schema requires quantity > 0
                {
                    **leg_data,
                    "quantity": abs(leg_data["quantity"])  # Use absolute value to ensure positive
                }
                for leg_data in self.legs_data
            ]
        }
        
        response = integration_client.post("/positions/with-legs", json=api_position)
        assert response.status_code == 201
        position_data = response.json()
        position_id = position_data["id"]
        
        # Verify persistence by querying the database directly
        db_position = db_session.query(Position).filter_by(id=position_id).first()
        assert db_position is not None
        assert db_position.name == api_position["name"]
        assert len(db_position.legs) == len(api_position["legs"])
        
        # Verify each leg was saved correctly
        for i, leg_data in enumerate(api_position["legs"]):
            db_leg = next((leg for leg in db_position.legs if leg.strike == leg_data["strike"] and leg.option_type == leg_data["option_type"]), None)
            assert db_leg is not None
            assert db_leg.option_price == leg_data["option_price"]
            assert db_leg.volatility == leg_data["volatility"]
        
        # Test updating via API
        update_data = {
            "name": "Updated via API",
            "description": "This position was updated through the API"
        }
        
        response = integration_client.put(f"/positions/with-legs/{position_id}", json=update_data)
        assert response.status_code == 200
        
        # Verify update in database
        db_session.expire_all()  # Refresh all instances
        updated_position = db_session.query(Position).filter_by(id=position_id).first()
        assert updated_position.name == "Updated via API"
        assert updated_position.description == "This position was updated through the API"
        
        # Test retrieving all positions via API
        response = integration_client.get("/positions/with-legs/")
        assert response.status_code == 200
        all_positions = response.json()
        # Check if our position is in the results
        assert any(p["id"] == position_id for p in all_positions)
        
        # Test retrieving a specific position by ID
        response = integration_client.get(f"/positions/with-legs/{position_id}")
        assert response.status_code == 200
        single_position = response.json()
        assert single_position["id"] == position_id
        assert single_position["name"] == "Updated via API"
        
        # Test deleting via API
        response = integration_client.delete(f"/positions/with-legs/{position_id}")
        assert response.status_code == 200
        
        # Verify deletion in database
        db_session.expire_all()  # Refresh all instances
        deleted_position = db_session.query(Position).filter_by(id=position_id).first()
        assert deleted_position is None 