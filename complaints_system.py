import sqlite3
import time
import json
from registration_aiogram import get_conn

def init_complaints_tables():
    """Initialize tables for complaints system"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Table for storing user messages
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message_text TEXT,
        media_type TEXT,
        media_file_id TEXT,
        timestamp INTEGER DEFAULT (strftime('%s', 'now')),
        chat_partner_id INTEGER
    )
    ''')
    
    # Table for storing complaints
    cur.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL,
        reported_user_id INTEGER NOT NULL,
        reason TEXT,
        timestamp INTEGER DEFAULT (strftime('%s', 'now')),
        status TEXT DEFAULT 'pending'
    )
    ''')
    
    # Table for blocked users
    cur.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        blocked_by INTEGER,
        reason TEXT,
        blocked_at INTEGER DEFAULT (strftime('%s', 'now'))
    )
    ''')
    
    conn.commit()
    conn.close()

def save_user_message(user_id, message_text=None, media_type=None, media_file_id=None, chat_partner_id=None):
    """Save user message to database"""
    init_complaints_tables()
    
    # Check if user has 18+ complaints - if so, save messages for review
    complaint_count = get_complaint_count(user_id)
    
    if complaint_count >= 18:  # Save messages when user has 18+ complaints
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute('''
        INSERT INTO user_messages (user_id, message_text, media_type, media_file_id, chat_partner_id)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, message_text, media_type, media_file_id, chat_partner_id))
        
        conn.commit()
        conn.close()

def has_user_complained_recently(reporter_id, reported_user_id):
    """Check if user has already complained about this user in current session"""
    # Allow complaints after each new conversation
    # Check if there's a complaint from the last 10 minutes (current session)
    conn = get_conn()
    cur = conn.cursor()
    
    current_time = int(time.time())
    ten_minutes_ago = current_time - 600  # 10 minutes
    
    cur.execute('''
    SELECT COUNT(*) FROM complaints 
    WHERE reporter_id = ? AND reported_user_id = ? AND timestamp > ?
    ''', (reporter_id, reported_user_id, ten_minutes_ago))
    
    count = cur.fetchone()[0]
    conn.close()
    
    return count > 0

def add_complaint(reporter_id, reported_user_id, reason="Порушення правил"):
    """Add complaint against user"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Add complaint
    cur.execute('''
    INSERT INTO complaints (reporter_id, reported_user_id, reason)
    VALUES (?, ?, ?)
    ''', (reporter_id, reported_user_id, reason))
    
    # Count total complaints for this user
    cur.execute('''
    SELECT COUNT(*) FROM complaints 
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (reported_user_id,))
    
    complaint_count = cur.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return complaint_count

def get_user_last_messages(user_id, limit=3):
    """Get last messages from user"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT message_text, media_type, media_file_id, timestamp, chat_partner_id
    FROM user_messages 
    WHERE user_id = ?
    ORDER BY timestamp DESC
    LIMIT ?
    ''', (user_id, limit))
    
    messages = cur.fetchall()
    conn.close()
    
    return messages

def get_complaint_count(user_id):
    """Get complaint count for user"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT COUNT(*) FROM complaints 
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (user_id,))
    
    count = cur.fetchone()[0]
    conn.close()
    
    return count

def block_user(user_id, blocked_by, reason="Порушення правил"):
    """Block user permanently"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Add to blocked users
    cur.execute('''
    INSERT OR REPLACE INTO blocked_users (user_id, blocked_by, reason)
    VALUES (?, ?, ?)
    ''', (user_id, blocked_by, reason))
    
    # Mark all complaints as resolved
    cur.execute('''
    UPDATE complaints 
    SET status = 'resolved_blocked'
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def ignore_complaints(user_id):
    """Ignore all complaints for user"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Mark all complaints as ignored
    cur.execute('''
    UPDATE complaints 
    SET status = 'ignored'
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def is_user_blocked(user_id):
    """Check if user is blocked"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT COUNT(*) FROM blocked_users WHERE user_id = ?
    ''', (user_id,))
    
    is_blocked = cur.fetchone()[0] > 0
    conn.close()
    
    return is_blocked

def unblock_user(user_id):
    """Unblock user"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Remove from blocked users
    cur.execute('DELETE FROM blocked_users WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

def get_users_with_complaints(min_complaints=10):
    """Get users with minimum number of complaints"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT reported_user_id, COUNT(*) as complaint_count
    FROM complaints 
    WHERE status = 'pending'
    GROUP BY reported_user_id
    HAVING complaint_count >= ?
    ORDER BY complaint_count DESC
    ''', (min_complaints,))
    
    users = cur.fetchall()
    conn.close()
    
    return users

def get_critical_period_messages(user_id, limit=50):
    """Get messages from critical period (18-20 complaints)"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT message_text, media_type, timestamp, chat_partner_id
    FROM user_messages 
    WHERE user_id = ?
    ORDER BY timestamp DESC
    LIMIT ?
    ''', (user_id, limit))
    
    messages = cur.fetchall()
    conn.close()
    
    return messages

def get_user_info_for_complaint(user_id):
    """Get user info for complaint review"""
    from registration_aiogram import get_user
    
    user_data = get_user(user_id)
    if not user_data:
        return None
    
    return {
        'user_id': user_id,
        'first_name': user_data.get('first_name', 'Невідомо'),
        'username': user_data.get('username', 'Немає'),
        'age': user_data.get('age', 'Невідомо'),
        'gender': user_data.get('gender', 'Невідомо'),
        'country': user_data.get('country', 'Невідомо')
    }

async def send_complaint_to_admin_bot(complainant_id, reported_user_id, complaint_text):
    """Send complaint notification to admin bot"""
    try:
        import os
        from dotenv import load_dotenv
        from aiogram import Bot
        
        # Load environment variables
        load_dotenv()
        
        # Токен адміністративного бота з .env файлу
        ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
        ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '8498395776'))
        
        if not ADMIN_BOT_TOKEN:
            print("ADMIN_BOT_TOKEN not found in .env file")
            return
        
        admin_bot = Bot(token=ADMIN_BOT_TOKEN)
        
        # Get user info
        complainant_info = get_user_info_for_complaint(complainant_id)
        reported_info = get_user_info_for_complaint(reported_user_id)
        
        # Format notification message
        notification_text = (
            f"🚨 **Нова скарга!**\n\n"
            f"👤 **Скаржник:**\n"
            f"• ID: {complainant_id}\n"
            f"• Ім'я: {complainant_info.get('first_name', 'Невідомо') if complainant_info else 'Невідомо'}\n"
            f"• Username: @{complainant_info.get('username', 'немає') if complainant_info else 'немає'}\n\n"
            f"🎯 **На користувача:**\n"
            f"• ID: {reported_user_id}\n"
            f"• Ім'я: {reported_info.get('first_name', 'Невідомо') if reported_info else 'Невідомо'}\n"
            f"• Username: @{reported_info.get('username', 'немає') if reported_info else 'немає'}\n"
            f"• Вік: {reported_info.get('age', 'Невідомо') if reported_info else 'Невідомо'}\n"
            f"• Стать: {reported_info.get('gender', 'Невідомо') if reported_info else 'Невідомо'}\n\n"
            f"📝 **Текст скарги:**\n{complaint_text}\n\n"
            f"⏰ **Час:** {time.strftime('%d.%m.%Y %H:%M', time.localtime())}"
        )
        
        await admin_bot.send_message(ADMIN_USER_ID, notification_text)
        await admin_bot.session.close()
        
    except Exception as e:
        # Якщо не вдалося надіслати в адмін бота, просто логуємо помилку
        print(f"Failed to send complaint to admin bot: {e}")

def get_required_channels():
    """Get list of required channels for subscription"""
    init_complaints_tables()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Create required_channels table if not exists
    cur.execute('''
    CREATE TABLE IF NOT EXISTS required_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_url TEXT,
        channel_name TEXT,
        channel_id TEXT,
        added_date INTEGER,
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    cur.execute('''
    SELECT channel_url, channel_name, channel_id
    FROM required_channels 
    WHERE is_active = 1
    ORDER BY added_date
    ''')
    
    channels = cur.fetchall()
    conn.close()
    
    return channels

async def check_user_subscriptions(user_id, bot):
    """Check if user is subscribed to all required channels"""
    channels = get_required_channels()
    
    if not channels:
        return True  # No required channels
    
    for channel_url, channel_name, channel_id in channels:
        try:
            if channel_id:
                # Check subscription using channel ID
                member = await bot.get_chat_member(channel_id, user_id)
                if member.status in ['left', 'kicked']:
                    return False
            else:
                # If no channel_id, assume user needs to subscribe
                return False
        except Exception:
            # If error checking subscription, assume not subscribed
            return False
    
    return True

def create_subscription_keyboard():
    """Create keyboard with required channels"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    channels = get_required_channels()
    
    if not channels:
        return None
    
    keyboard_buttons = []
    
    for channel_url, channel_name, channel_id in channels:
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"📺 {channel_name}", url=channel_url)
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="✅ Я підписався", callback_data="check_subscriptions")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
