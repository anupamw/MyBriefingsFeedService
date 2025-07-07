#!/usr/bin/env python3
"""
Script to fix the Perplexity model name in the database
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database.connection import SessionLocal
from shared.models.database_models import DataSource

def fix_perplexity_model():
    """Update the Perplexity data source model name"""
    db = SessionLocal()
    
    try:
        # Find the Perplexity data source
        perplexity_source = db.query(DataSource).filter(
            DataSource.name == "perplexity"
        ).first()
        
        if perplexity_source:
            print(f"Found Perplexity data source: {perplexity_source.display_name}")
            print(f"Current config: {perplexity_source.config}")
            
            # Update the model name
            if perplexity_source.config:
                perplexity_source.config["model"] = "sonar"
            else:
                perplexity_source.config = {"model": "sonar"}
            
            db.commit()
            print("✅ Updated Perplexity model name to 'sonar'")
            print(f"New config: {perplexity_source.config}")
        else:
            print("❌ Perplexity data source not found")
            
    except Exception as e:
        print(f"❌ Error updating Perplexity model: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    load_dotenv()
    fix_perplexity_model() 