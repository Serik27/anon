import sqlite3
import logging
import time
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Keyboards
def get_gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='👨 Чоловік'), KeyboardButton(text='👩 Жінка')]],
        resize_keyboard=True
    )

def get_conn():
    """Get a database connection"""
    return sqlite3.connect('users.db')

def init_db():
    """Initialize database with all required tables"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Create users table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        gender TEXT,
        age INTEGER,
        country TEXT,
        username TEXT,
        first_name TEXT,
        registration_date TEXT,
        total_chat_time INTEGER DEFAULT 0,
        premium_until INTEGER DEFAULT 0,
        pro_until INTEGER DEFAULT 0,
        pro_anonymous INTEGER DEFAULT 0,
        media_blur INTEGER DEFAULT 0
    )
    ''')
    
    # Add media_blur column if it doesn't exist (for existing databases)
    try:
        cur.execute('ALTER TABLE users ADD COLUMN media_blur INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add total_chat_time column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN total_chat_time INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add username column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN username TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add first_name column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN first_name TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add pro_until column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN pro_until INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add pro_anonymous column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN pro_anonymous INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create search_preferences table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS search_preferences (
        user_id INTEGER,
        preference_type TEXT,
        preference_value TEXT,
        PRIMARY KEY (user_id, preference_type)
    )
    ''')
    
    # Create statistics table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        user_id INTEGER PRIMARY KEY,
        messages_sent INTEGER DEFAULT 0,
        chats_count INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create ratings table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        user_id INTEGER,
        rating_type TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, rating_type),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create reports table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER,
        reported_id INTEGER,
        reason TEXT,
        report_date INTEGER,
        FOREIGN KEY (reporter_id) REFERENCES users(user_id),
        FOREIGN KEY (reported_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create referrals table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        date INTEGER,
        FOREIGN KEY (referrer_id) REFERENCES users(user_id),
        FOREIGN KEY (referred_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create weekly_prizes table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS weekly_prizes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        prize_type TEXT,
        week_start INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create friends table for PRO users
    cur.execute('''
    CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        friend_id INTEGER,
        friend_name TEXT,
        added_date INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (friend_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create user_activity table to track online status
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id INTEGER PRIMARY KEY,
        last_activity INTEGER,
        is_chatting INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create hourly_activity_stats table for tracking activity by hours
    cur.execute('''
    CREATE TABLE IF NOT EXISTS hourly_activity_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        activity_hour INTEGER,
        activity_date TEXT,
        activity_timestamp INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create activity_notifications_sent table for tracking sent notifications
    cur.execute('''
    CREATE TABLE IF NOT EXISTS activity_notifications_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        notification_timestamp INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create settings table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at INTEGER
    )
    ''')
    
    # Insert default notification threshold if not exists
    cur.execute('''
    INSERT OR IGNORE INTO settings (key, value, updated_at) 
    VALUES ('notification_threshold', '10000', ?)
    ''', (int(time.time()),))
    
    # Create blocked_users table for admin bot compatibility
    cur.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY,
        blocked_by INTEGER NOT NULL DEFAULT 0,
        reason TEXT,
        timestamp INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def save_user(user_id, gender, age, country, username=None, first_name=None):
    """Save user registration data"""
    conn = get_conn()
    cur = conn.cursor()
    
    registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute('''
    INSERT OR REPLACE INTO users 
    (user_id, gender, age, country, registration_date, total_chat_time, premium_until, username, first_name)
    VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
    ''', (user_id, gender, age, country, registration_date, username, first_name))
    
    # Initialize statistics
    cur.execute('''
    INSERT OR IGNORE INTO statistics (user_id, messages_sent, chats_count)
    VALUES (?, 0, 0)
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    
    logging.info(f"User {user_id} registered successfully")

def get_user(user_id):
    """Get user data"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT user_id, gender, age, country, registration_date, total_chat_time, premium_until, username, first_name
    FROM users WHERE user_id = ?
    ''', (user_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            'user_id': row[0],
            'gender': row[1],
            'age': row[2],
            'country': row[3],
            'registration_date': row[4],
            'total_chat_time': row[5],
            'premium_until': row[6],
            'username': row[7],
            'first_name': row[8]
        }
    return None

def get_user_by_username(username):
    """Get user data by username"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT user_id, gender, age, country, registration_date, total_chat_time, premium_until, username, first_name
    FROM users WHERE username = ?
    ''', (username,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            'user_id': row[0],
            'gender': row[1],
            'age': row[2],
            'country': row[3],
            'registration_date': row[4],
            'total_chat_time': row[5],
            'premium_until': row[6],
            'username': row[7],
            'first_name': row[8]
        }
    return None

def update_user_premium(user_id, premium_until):
    """Update user premium status"""
    conn = get_conn()
    cur = conn.cursor()
    
    query = 'UPDATE users SET premium_until = ? WHERE user_id = ?'
    cur.execute(query, (premium_until, user_id))
    
    conn.commit()
    conn.close()

def update_user_info(user_id, username=None, first_name=None):
    """Update user's username and first_name if they changed"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get current data
        cur.execute('SELECT username, first_name FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        
        if row:
            current_username, current_first_name = row
            
            # Update if changed
            if username != current_username or first_name != current_first_name:
                cur.execute('''
                UPDATE users SET username = ?, first_name = ? 
                WHERE user_id = ?
                ''', (username, first_name, user_id))
                conn.commit()
                logging.info(f"Updated user info for {user_id}: username={username}, first_name={first_name}")
        
    except Exception as e:
        logging.error(f"Error updating user info for {user_id}: {e}")
    finally:
        conn.close()

def is_user_blocked(user_id):
    """Check if user is blocked by admin"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT 1 FROM blocked_users WHERE user_id = ?', (user_id,))
        is_blocked = bool(cur.fetchone())
        return is_blocked
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return False
    finally:
        conn.close()

def get_user_stats(user_id):
    """Get user statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT messages_sent, chats_count
    FROM statistics WHERE user_id = ?
    ''', (user_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            'messages_sent': row[0],
            'chats_count': row[1]
        }
    return {'messages_sent': 0, 'chats_count': 0}

def update_user_stats(user_id, messages_sent=None, chats_count=None):
    """Update user statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    if messages_sent is not None:
        cur.execute('''
        UPDATE statistics SET messages_sent = messages_sent + ?
        WHERE user_id = ?
        ''', (messages_sent, user_id))
    
    if chats_count is not None:
        cur.execute('''
        UPDATE statistics SET chats_count = chats_count + ?
        WHERE user_id = ?
        ''', (chats_count, user_id))
    
    conn.commit()
    conn.close()

def get_all_users():
    """Get all registered users"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT user_id FROM users')
    rows = cur.fetchall()
    conn.close()
    
    return [row[0] for row in rows]

def delete_user(user_id):
    """Delete user and all related data"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Delete from all tables
    tables = ['users', 'statistics', 'ratings', 'reports', 'referrals', 'weekly_prizes']
    
    for table in tables:
        if table in ['reports', 'referrals']:
            # These tables have both reporter/referrer and reported/referred
            cur.execute(f'DELETE FROM {table} WHERE reporter_id = ? OR reported_id = ?', (user_id, user_id))
        elif table == 'weekly_prizes':
            cur.execute(f'DELETE FROM {table} WHERE user_id = ?', (user_id,))
        else:
            cur.execute(f'DELETE FROM {table} WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    logging.info(f"User {user_id} deleted successfully")

def get_users_count():
    """Get total number of registered users"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM users')
    count = cur.fetchone()[0]
    conn.close()
    
    return count

def search_users_by_criteria(gender=None, min_age=None, max_age=None, country=None, interests=None):
    """Search users by various criteria"""
    conn = get_conn()
    cur = conn.cursor()
    
    query = 'SELECT user_id FROM users WHERE 1=1'
    params = []
    
    if gender:
        query += ' AND gender = ?'
        params.append(gender)
    
    if min_age:
        query += ' AND age >= ?'
        params.append(min_age)
    
    if max_age:
        query += ' AND age <= ?'
        params.append(max_age)
    
    if country:
        query += ' AND country = ?'
        params.append(country)
    
    if interests:
        for interest in interests:
            query += ' AND interests LIKE ?'
            params.append(f'%{interest}%')
    
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return [row[0] for row in rows]

def add_report(reporter_id, reported_id, reason):
    """Add a user report"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT INTO reports (reporter_id, reported_id, reason, report_date)
    VALUES (?, ?, ?, ?)
    ''', (reporter_id, reported_id, reason, int(time.time())))
    
    conn.commit()
    conn.close()
    
    logging.info(f"User {reporter_id} reported user {reported_id} for: {reason}")

def get_user_reports(user_id):
    """Get all reports for a specific user"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT reporter_id, reason, report_date
    FROM reports WHERE reported_id = ?
    ORDER BY report_date DESC
    ''', (user_id,))
    
    rows = cur.fetchall()
    conn.close()
    
    return [{'reporter_id': row[0], 'reason': row[1], 'report_date': row[2]} for row in rows]

def get_reports_count(user_id):
    """Get number of reports for a user"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM reports WHERE reported_id = ?', (user_id,))
    count = cur.fetchone()[0]
    conn.close()
    
    return count
