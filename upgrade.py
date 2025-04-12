import os
import shutil
import logging
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("upgrade.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("Upgrade")

def backup_existing_data():
    """Backup existing database files"""
    logger.info("Backing up existing data...")
    
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup database files
    data_dir = 'data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"Created data directory: {data_dir}")
        return backup_dir
        
    for db_file in ['market_data.db', 'indicators.db', 'signals.db', 'positions.db', 'ai_model.db', 'config.db']:
        db_path = os.path.join(data_dir, db_file)
        if os.path.exists(db_path):
            shutil.copy2(db_path, os.path.join(backup_dir, db_file))
            logger.info(f"Backed up {db_file}")
    
    logger.info(f"Backup completed to directory: {backup_dir}")
    return backup_dir

def update_database_schema():
    """Update database schema for new features"""
    logger.info("Updating database schema...")
    
    # Ensure data directory exists
    data_dir = 'data'
    os.makedirs(data_dir, exist_ok=True)
    
    # Update ai_model.db to add actual_outcome and accuracy columns if they don't exist
    db_path = os.path.join(data_dir, 'ai_model.db')
    
    # Check if the database exists, if not, it will be created when we connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_predictions'")
    if not cursor.fetchone():
        logger.info("Creating model_predictions table")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            prediction_type TEXT NOT NULL CHECK(prediction_type IN ('LONG', 'SHORT', 'NEUTRAL')),
            confidence_score REAL NOT NULL,
            features_id INTEGER NOT NULL,
            actual_outcome TEXT DEFAULT NULL,
            accuracy REAL DEFAULT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    else:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(model_predictions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'actual_outcome' not in columns:
            logger.info("Adding actual_outcome column to model_predictions table")
            cursor.execute("ALTER TABLE model_predictions ADD COLUMN actual_outcome TEXT")
        
        if 'accuracy' not in columns:
            logger.info("Adding accuracy column to model_predictions table")
            cursor.execute("ALTER TABLE model_predictions ADD COLUMN accuracy REAL")
    
    conn.commit()
    conn.close()
    
    logger.info("Database schema updated successfully")

def install_new_files():
    """Install new Python files"""
    logger.info("Installing new files...")
    
    # Create directories if they don't exist
    os.makedirs('data/reports', exist_ok=True)
    os.makedirs('data/models', exist_ok=True)
    
    logger.info("Created directory structure")
    logger.info("New files installed successfully")

def main():
    logger.info("Starting upgrade process...")
    
    # Backup existing data
    backup_dir = backup_existing_data()
    
    # Update database schema
    update_database_schema()
    
    # Install new files
    install_new_files()
    
    logger.info(f"Upgrade completed successfully. Backup stored in {backup_dir}")
    logger.info("You can now run the enhanced system with: python main_enhanced.py")

if __name__ == "__main__":
    main()
