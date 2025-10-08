import sqlite3
import time
from registration_aiogram import get_conn

def init_rooms_tables():
    """Initialize tables for rooms system"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Table for room status
    cur.execute('''
    CREATE TABLE IF NOT EXISTS room_status (
        room_id TEXT PRIMARY KEY,
        room_name TEXT NOT NULL,
        is_open INTEGER DEFAULT 1,
        closed_by INTEGER,
        closed_at INTEGER
    )
    ''')
    
    # Table for user room preferences
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_rooms (
        user_id INTEGER PRIMARY KEY,
        current_room TEXT DEFAULT 'room_general',
        FOREIGN KEY (current_room) REFERENCES room_status(room_id)
    )
    ''')
    
    # Initialize default rooms if not exist
    rooms = [
        ('room_general', '💬 Общение'),
        ('room_exchange', '🔞 Обмен 18+'),
        ('room_lgbt', '🏳️‍🌈 ЛГБТ'),
        ('room_school', '🎓 Школа')
    ]
    
    for room_id, room_name in rooms:
        cur.execute('''
        INSERT OR IGNORE INTO room_status (room_id, room_name, is_open)
        VALUES (?, ?, 1)
        ''', (room_id, room_name))
    
    conn.commit()
    conn.close()

def is_room_open(room_id):
    """Check if room is open"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT is_open FROM room_status WHERE room_id = ?', (room_id,))
    result = cur.fetchone()
    conn.close()
    
    return result[0] == 1 if result else False

def close_room(room_id, admin_id):
    """Close room and move all users to general room"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    # Close the room
    cur.execute('''
    UPDATE room_status 
    SET is_open = 0, closed_by = ?, closed_at = ?
    WHERE room_id = ?
    ''', (admin_id, int(time.time()), room_id))
    
    # Move all users from closed room to general room
    cur.execute('''
    UPDATE user_rooms 
    SET current_room = 'room_general'
    WHERE current_room = ?
    ''', (room_id,))
    
    # Get count of moved users
    cur.execute('''
    SELECT COUNT(*) FROM user_rooms 
    WHERE current_room = 'room_general'
    ''')
    moved_count = cur.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return moved_count

def open_room(room_id, admin_id):
    """Open room"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    UPDATE room_status 
    SET is_open = 1, closed_by = NULL, closed_at = NULL
    WHERE room_id = ?
    ''', (room_id,))
    
    conn.commit()
    conn.close()

def get_user_room(user_id):
    """Get user's current room"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT current_room FROM user_rooms WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    
    if not result:
        # Set default room for new user
        cur.execute('''
        INSERT INTO user_rooms (user_id, current_room)
        VALUES (?, 'room_general')
        ''', (user_id,))
        conn.commit()
        conn.close()
        return 'room_general'
    
    conn.close()
    return result[0]

def set_user_room(user_id, room_id):
    """Set user's current room"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT OR REPLACE INTO user_rooms (user_id, current_room)
    VALUES (?, ?)
    ''', (user_id, room_id))
    
    conn.commit()
    conn.close()

def get_room_info(room_id):
    """Get room information"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT room_name, is_open, closed_by, closed_at
    FROM room_status 
    WHERE room_id = ?
    ''', (room_id,))
    
    result = cur.fetchone()
    conn.close()
    
    if result:
        return {
            'name': result[0],
            'is_open': result[1] == 1,
            'closed_by': result[2],
            'closed_at': result[3]
        }
    return None

def get_all_rooms():
    """Get all rooms with their status"""
    init_rooms_tables()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT room_id, room_name, is_open
    FROM room_status
    ORDER BY room_id
    ''')
    
    rooms = cur.fetchall()
    conn.close()
    
    return rooms
