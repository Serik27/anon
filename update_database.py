#!/usr/bin/env python3
"""
Script to update database schema for admin commands support
"""

import sqlite3
import os

def update_database():
    """Update database schema to add username and first_name columns"""
    db_path = 'users.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # Check current table structure
        cur.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add username column if it doesn't exist
        if 'username' not in columns:
            print("Adding username column...")
            cur.execute('ALTER TABLE users ADD COLUMN username TEXT')
            print("OK Username column added")
        else:
            print("OK Username column already exists")
        
        # Add first_name column if it doesn't exist
        if 'first_name' not in columns:
            print("Adding first_name column...")
            cur.execute('ALTER TABLE users ADD COLUMN first_name TEXT')
            print("OK First_name column added")
        else:
            print("OK First_name column already exists")
        
        conn.commit()
        
        # Check updated structure
        cur.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        print(f"Updated columns: {columns}")
        
        # Show sample data
        cur.execute("SELECT user_id, username, first_name FROM users LIMIT 5")
        rows = cur.fetchall()
        print(f"\nSample data:")
        for row in rows:
            print(f"  User ID: {row[0]}, Username: {row[1]}, First Name: {row[2]}")
        
        print("\nOK Database update completed successfully!")
        
    except Exception as e:
        print(f"ERROR updating database: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    update_database()
