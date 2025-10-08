import asyncio
import time
from datetime import datetime, timedelta
from registration_aiogram import get_conn
import logging

logger = logging.getLogger(__name__)

def get_notification_threshold():
    """Get current notification threshold from database"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT setting_value FROM bot_settings WHERE setting_key = ?', ('notification_threshold',))
        result = cur.fetchone()
        conn.close()
        
        if result:
            return int(result[0])
        else:
            # Return default if not found
            return 10000
            
    except Exception as e:
        logger.error(f"Error getting notification threshold: {e}")
        conn.close()
        return 10000

def set_notification_threshold(threshold):
    """Set notification threshold in database"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        current_time = int(time.time())
        cur.execute('''
        INSERT OR REPLACE INTO bot_settings (setting_key, setting_value, updated_timestamp)
        VALUES ('notification_threshold', ?, ?)
        ''', (str(threshold), current_time))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error setting notification threshold: {e}")
        conn.close()
        return False

def should_send_notification(user_id):
    """Check if user should receive activity notification"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check if user was active in last 12 hours
        current_time = int(time.time())
        inactive_threshold = current_time - (12 * 3600)  # 12 hours ago
        
        cur.execute('''
        SELECT last_activity FROM user_activity 
        WHERE user_id = ? AND last_activity > ?
        ''', (user_id, inactive_threshold))
        
        if cur.fetchone():
            # User was active in last 12 hours, don't send notification
            conn.close()
            return False
        
        # Check if notification was already sent today
        today = datetime.now().date().strftime('%Y-%m-%d')
        cur.execute('''
        SELECT 1 FROM activity_notifications_sent 
        WHERE user_id = ? AND notification_date = ?
        ''', (user_id, today))
        
        if cur.fetchone():
            # Notification already sent today
            conn.close()
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error checking notification status for user {user_id}: {e}")
        conn.close()
        return False

def mark_notification_sent(user_id):
    """Mark that notification was sent to user"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        current_time = int(time.time())
        today = datetime.now().date().strftime('%Y-%m-%d')
        
        cur.execute('''
        INSERT INTO activity_notifications_sent (user_id, notification_date, notification_timestamp)
        VALUES (?, ?, ?)
        ''', (user_id, today, current_time))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error marking notification sent for user {user_id}: {e}")
        conn.close()

def get_inactive_users():
    """Get list of users who haven't been active in last 12 hours"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        current_time = int(time.time())
        inactive_threshold = current_time - (12 * 3600)  # 12 hours ago
        
        # Get users who either have no activity record or were inactive for 12+ hours
        cur.execute('''
        SELECT u.user_id, u.first_name, u.username
        FROM users u
        LEFT JOIN user_activity ua ON u.user_id = ua.user_id
        WHERE ua.last_activity IS NULL OR ua.last_activity <= ?
        ''', (inactive_threshold,))
        
        users = cur.fetchall()
        conn.close()
        
        return [(user_id, first_name, username) for user_id, first_name, username in users]
        
    except Exception as e:
        logger.error(f"Error getting inactive users: {e}")
        conn.close()
        return []

def get_current_activity_stats():
    """Get current activity statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        current_time = int(time.time())
        active_threshold = current_time - 300  # 5 minutes
        
        # Get active users count
        cur.execute('''
        SELECT COUNT(*) FROM user_activity 
        WHERE last_activity > ?
        ''', (active_threshold,))
        
        active_count = cur.fetchone()[0]
        
        # Get waiting users count
        cur.execute('SELECT COUNT(*) FROM waiting_users')
        waiting_count = cur.fetchone()[0]
        
        conn.close()
        
        return active_count, waiting_count
        
    except Exception as e:
        logger.error(f"Error getting activity stats: {e}")
        conn.close()
        return 0, 0

async def send_activity_notifications(min_active_users=None):
    """Send activity notifications to inactive users"""
    try:
        # Get threshold from database if not provided
        if min_active_users is None:
            min_active_users = get_notification_threshold()
        
        # Get current activity stats
        active_count, waiting_count = get_current_activity_stats()
        
        # Only send notifications if there's significant activity (use threshold from DB)
        if active_count < min_active_users:
            logger.info(f"Not enough activity to send notifications: {active_count} active, threshold: {min_active_users}")
            return False
        
        # Get inactive users
        inactive_users = get_inactive_users()
        
        if not inactive_users:
            logger.info("No inactive users found")
            return False
        
        # Filter users who should receive notifications
        users_to_notify = []
        for user_id, first_name, username in inactive_users:
            if should_send_notification(user_id):
                users_to_notify.append((user_id, first_name, username))
        
        if not users_to_notify:
            logger.info("No users need activity notifications")
            return False
        
        # Create notification message
        notification_text = (
            f"🔥 **Велика активність в боті!**\n\n"
            f"👥 Зараз активно: **{active_count}** користувачів\n"
            f"🔍 Шукають співрозмовника: **{waiting_count}** осіб\n\n"
            f"💬 Це чудовий час для пошуку нових знайомств!\n"
            f"Натисніть /search щоб почати спілкування."
        )
        
        # Send notifications
        from bot_aiogram import bot
        successful_sends = 0
        
        for user_id, first_name, username in users_to_notify:
            try:
                await bot.send_message(user_id, notification_text)
                mark_notification_sent(user_id)
                successful_sends += 1
                
                # Small delay to avoid hitting rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")
        
        logger.info(f"Sent activity notifications to {successful_sends}/{len(users_to_notify)} users (threshold: {min_active_users})")
        return True
        
    except Exception as e:
        logger.error(f"Error in send_activity_notifications: {e}")
        return False

async def check_and_send_notifications():
    """Check current activity and send notifications if threshold is reached"""
    try:
        threshold = get_notification_threshold()
        active_count, waiting_count = get_current_activity_stats()
        
        if active_count >= threshold:
            logger.info(f"Activity threshold reached: {active_count}/{threshold} - sending notifications")
            await send_activity_notifications()
        else:
            logger.debug(f"Activity below threshold: {active_count}/{threshold}")
            
    except Exception as e:
        logger.error(f"Error in check_and_send_notifications: {e}")

async def start_activity_notification_scheduler():
    """Start the activity notification scheduler"""
    logger.info("Starting activity notification scheduler - checking every 30 minutes")
    
    while True:
        try:
            # Check activity and send notifications if threshold is reached
            await check_and_send_notifications()
            
            # Wait 30 minutes before next check
            await asyncio.sleep(30 * 60)
                
        except Exception as e:
            logger.error(f"Error in activity notification scheduler: {e}")
            # Wait 5 minutes before retrying
            await asyncio.sleep(5 * 60)
