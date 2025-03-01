"""
Database upgrade script to add new columns for volatility calculations.
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def upgrade_database():
    """Add new columns to the position_pnl_results table if they don't exist."""
    db_path = 'options.db'
    
    # Ensure the database file exists
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found.")
        return
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the columns exist
    columns_to_add = {
        'historical_volatility': 'REAL',
        'volatility_days': 'INTEGER'
    }
    
    # Get existing columns
    cursor.execute(f"PRAGMA table_info(position_pnl_results)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # Add missing columns
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                print(f"Adding column {column_name} to position_pnl_results table...")
                cursor.execute(f"ALTER TABLE position_pnl_results ADD COLUMN {column_name} {column_type}")
                print(f"Column {column_name} added successfully.")
            except sqlite3.Error as e:
                print(f"Error adding column {column_name}: {e}")
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Database upgrade completed.")

if __name__ == "__main__":
    upgrade_database()
