import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import types
from aiogram.filters import Command
from aiogram.types import Message

# Import from existing modules
from registration_aiogram import get_conn
from maintenance import enable_maintenance, disable_maintenance

# Get admin ID from environment
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID

def get_user_by_username(username: str):
    """Get user by username"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Remove @ if present
    username = username.lstrip('@')
    
    try:
        cur.execute('''
        SELECT user_id, username, first_name FROM users 
        WHERE username = ? COLLATE NOCASE
        ''', (username,))
        
        result = cur.fetchone()
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2]
            }
        return None
    except sqlite3.OperationalError as e:
        conn.close()
        print(f"Database error in get_user_by_username: {e}")
        return None

def get_user_by_id(user_id: int):
    """Get user by ID"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('''
        SELECT user_id, username, first_name FROM users 
        WHERE user_id = ?
        ''', (user_id,))
        
        result = cur.fetchone()
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2]
            }
        return None
    except sqlite3.OperationalError as e:
        conn.close()
        print(f"Database error in get_user_by_id: {e}")
        return None

async def admin_set_premium(message: Message):
    """Admin command to set premium for user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/set_premium <user_id/username> <кількість> <одиниця>`\n\n"
            "**Одиниці часу:**\n"
            "• `m` - хвилини\n"
            "• `h` - години\n" 
            "• `d` - дні\n"
            "• `f` - назавжди\n\n"
            "**Приклади:**\n"
            "`/set_premium @username 15 m` - 15 хвилин\n"
            "`/set_premium 123456789 2 h` - 2 години\n"
            "`/set_premium @username 7 d` - 7 днів\n"
            "`/set_premium @username 1 f` - назавжди"
        )
        return
    
    if len(args) < 3:
        await message.answer("❌ Недостатньо аргументів. Використайте: `/set_premium <user> <кількість> <одиниця>`")
        return
    
    target_user = args[0]
    user_data = None
    
    # Check if it's username or user_id
    if target_user.startswith('@'):
        user_data = get_user_by_username(target_user)
    else:
        try:
            user_id = int(target_user)
            user_data = get_user_by_id(user_id)
        except ValueError:
            # Maybe it's username without @
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Parse duration
    try:
        amount = int(args[1])
        unit = args[2].lower()
    except ValueError:
        await message.answer("❌ Неправильний формат кількості. Використайте число.")
        return
    
    # Calculate total duration in seconds
    total_seconds = 0
    duration_text = ""
    
    if unit == 'f':  # forever
        total_seconds = 50 * 365 * 24 * 3600  # 50 years
        duration_text = "назавжди"
    elif unit == 'm':  # minutes
        total_seconds = amount * 60
        duration_text = f"{amount} хв."
    elif unit == 'h':  # hours
        total_seconds = amount * 3600
        duration_text = f"{amount} год."
    elif unit == 'd':  # days
        total_seconds = amount * 24 * 3600
        duration_text = f"{amount} дн."
    else:
        await message.answer("❌ Невідома одиниця часу. Використайте: m (хвилини), h (години), d (дні), f (назавжди)")
        return
    
    if total_seconds <= 0 and unit != 'f':
        await message.answer("❌ Тривалість преміум повинна бути більше 0.")
        return
    
    # Set premium status using the premium_until field in users table
    import time
    current_time = int(time.time())
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current premium_until value
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_data['user_id'],))
    row = cur.fetchone()
    current_until = row[0] if row and row[0] else 0
    
    # Add time to current premium or start from now
    new_until = max(current_time, current_until) + total_seconds
    
    # Update users table
    cur.execute('UPDATE users SET premium_until = ? WHERE user_id = ?', (new_until, user_data['user_id']))
    
    conn.commit()
    conn.close()
    
    # Format end date
    if unit == 'f':
        end_date_text = "Назавжди"
    else:
        end_date = datetime.fromtimestamp(new_until)
        end_date_text = end_date.strftime('%d.%m.%Y %H:%M')
    
    # Format user info
    user_info = f"ID: {user_data['user_id']}"
    if user_data['username']:
        user_info += f" (@{user_data['username']})"
    if user_data['first_name']:
        user_info += f" - {user_data['first_name']}"
    
    await message.answer(
        f"✅ **Преміум надано!**\n\n"
        f"👤 **Користувач:** {user_info}\n"
        f"⏰ **Тривалість:** {duration_text}\n"
        f"📅 **До:** {end_date_text}"
    )

async def admin_remove_premium(message: Message):
    """Admin command to remove premium from user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/remove_premium <user_id>` - забрати преміум за ID\n"
            "`/remove_premium @username` - забрати преміум за username\n\n"
            "**Приклади:**\n"
            "`/remove_premium 123456789`\n"
            "`/remove_premium @username`"
        )
        return
    
    target_user = args[0]
    user_data = None
    
    # Check if it's username or user_id
    if target_user.startswith('@'):
        user_data = get_user_by_username(target_user)
    else:
        try:
            user_id = int(target_user)
            user_data = get_user_by_id(user_id)
        except ValueError:
            # Maybe it's username without @
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Remove premium status
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if user has premium
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_data['user_id'],))
    row = cur.fetchone()
    
    if not row or not row[0] or row[0] <= int(__import__('time').time()):
        await message.answer("❌ Користувач не має преміум статусу.")
        conn.close()
        return
    
    # Remove premium by setting premium_until to 0
    cur.execute('UPDATE users SET premium_until = 0 WHERE user_id = ?', (user_data['user_id'],))
    conn.commit()
    conn.close()
    
    # Format user info
    user_info = f"ID: {user_data['user_id']}"
    if user_data['username']:
        user_info += f" (@{user_data['username']})"
    if user_data['first_name']:
        user_info += f" - {user_data['first_name']}"
    
    await message.answer(
        f"✅ **Преміум забрано!**\n\n"
        f"👤 **Користувач:** {user_info}\n"
        f"📅 **Статус:** Звичайний користувач"
    )

async def admin_stats(message: Message):
    """Admin command to get bot statistics"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get total users
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    
    # Get premium and PRO users
    current_time = int(__import__('time').time())
    cur.execute('SELECT COUNT(*) FROM users WHERE premium_until > ?', (current_time,))
    premium_users = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM users WHERE pro_until > ?', (current_time,))
    pro_users = cur.fetchone()[0]
    
    # Get active chats
    cur.execute('SELECT COUNT(*) FROM active_chats')
    active_chats = cur.fetchone()[0] // 2  # Divide by 2 because each chat has 2 entries
    
    # Get waiting users
    cur.execute('SELECT COUNT(*) FROM waiting_users')
    waiting_users = cur.fetchone()[0]
    
    # Get today's registrations
    today = datetime.now().date()
    cur.execute('SELECT COUNT(*) FROM users WHERE DATE(registration_date) = ?', (today,))
    today_registrations = cur.fetchone()[0]
    
    conn.close()
    
    # Calculate total paid users
    total_paid_users = premium_users + pro_users
    
    await message.answer(
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всього користувачів:** {total_users}\n"
        f"🌟 **PRO користувачів:** {pro_users}\n"
        f"💎 **Преміум користувачів:** {premium_users}\n"
        f"💰 **Всього платних:** {total_paid_users}\n"
        f"💬 **Активних чатів:** {active_chats}\n"
        f"🔍 **Шукають співрозмовника:** {waiting_users}\n"
        f"📅 **Реєстрацій сьогодні:** {today_registrations}\n\n"
        f"📈 **Конверсія в платні:** {(total_paid_users/total_users*100):.1f}%" if total_users > 0 else "📈 **Конверсія в платні:** 0%"
    )

async def admin_user_info(message: Message):
    """Admin command to get user information"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/user_info <user_id>` - інформація за ID\n"
            "`/user_info @username` - інформація за username"
        )
        return
    
    target_user = args[0]
    user_data = None
    
    # Check if it's username or user_id
    if target_user.startswith('@'):
        user_data = get_user_by_username(target_user)
    else:
        try:
            user_id = int(target_user)
            user_data = get_user_by_id(user_id)
        except ValueError:
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Get detailed user info
    conn = get_conn()
    cur = conn.cursor()
    
    # Get full user data
    cur.execute('''
    SELECT user_id, username, first_name, gender, age, country, registration_date
    FROM users WHERE user_id = ?
    ''', (user_data['user_id'],))
    
    full_user_data = cur.fetchone()
    
    # Check premium and PRO status - get all status info
    current_time = int(__import__('time').time())
    cur.execute('SELECT premium_until, pro_until FROM users WHERE user_id = ?', (user_data['user_id'],))
    status_row = cur.fetchone()
    premium_until = status_row[0] if status_row and status_row[0] else 0
    pro_until = status_row[1] if status_row and status_row[1] else 0
    
    # Get statistics
    cur.execute('SELECT messages_sent, chats_count FROM statistics WHERE user_id = ?', 
                (user_data['user_id'],))
    stats_data = cur.fetchone()
    
    # Get referral count
    cur.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_data['user_id'],))
    referral_row = cur.fetchone()
    referral_count = referral_row[0] if referral_row else 0
    
    conn.close()
    
    if not full_user_data:
        await message.answer("❌ Повні дані користувача не знайдено.")
        return
    
    # Format response
    user_id, username, first_name, gender, age, country, reg_date = full_user_data
    
    info_text = f"👤 **Інформація про користувача**\n\n"
    info_text += f"🆔 **ID:** {user_id}\n"
    
    if username:
        info_text += f"📝 **Username:** @{username}\n"
    if first_name:
        info_text += f"👋 **Ім'я:** {first_name}\n"
    if gender:
        info_text += f"⚧ **Стать:** {gender}\n"
    if age:
        info_text += f"🎂 **Вік:** {age}\n"
    if country:
        info_text += f"🌍 **Країна:** {country}\n"
    
    if reg_date:
        info_text += f"📅 **Реєстрація:** {reg_date}\n"
    
    # Status information with detailed info
    info_text += f"\n📊 **Статус користувача:**\n"
    
    # Check PRO status first (higher priority)
    if pro_until and pro_until > current_time:
        end_date = datetime.fromtimestamp(pro_until)
        remaining_seconds = pro_until - current_time
        
        # Calculate remaining time
        days = remaining_seconds // (24 * 3600)
        hours = (remaining_seconds % (24 * 3600)) // 3600
        minutes = (remaining_seconds % 3600) // 60
        
        if days > 0:
            time_left = f"{days} дн. {hours} год."
        elif hours > 0:
            time_left = f"{hours} год. {minutes} хв."
        else:
            time_left = f"{minutes} хв."
        
        info_text += f"🌟 **Активний PRO статус**\n"
        info_text += f"📅 **Закінчується:** {end_date.strftime('%d.%m.%Y %H:%M')}\n"
        info_text += f"⏰ **Залишилось:** {time_left}\n"
        
    elif premium_until and premium_until > current_time:
        end_date = datetime.fromtimestamp(premium_until)
        remaining_seconds = premium_until - current_time
        
        # Calculate remaining time
        days = remaining_seconds // (24 * 3600)
        hours = (remaining_seconds % (24 * 3600)) // 3600
        minutes = (remaining_seconds % 3600) // 60
        
        if days > 0:
            time_left = f"{days} дн. {hours} год."
        elif hours > 0:
            time_left = f"{hours} год. {minutes} хв."
        else:
            time_left = f"{minutes} хв."
        
        info_text += f"💎 **Активний преміум**\n"
        info_text += f"📅 **Закінчується:** {end_date.strftime('%d.%m.%Y %H:%M')}\n"
        info_text += f"⏰ **Залишилось:** {time_left}\n"
        
    else:
        info_text += f"👤 **Звичайний користувач**\n"
        
        # Show expired statuses
        if pro_until > 0:
            expired_date = datetime.fromtimestamp(pro_until)
            info_text += f"🌟 **PRO закінчився:** {expired_date.strftime('%d.%m.%Y %H:%M')}\n"
        if premium_until > 0:
            expired_date = datetime.fromtimestamp(premium_until)
            info_text += f"💎 **Преміум закінчився:** {expired_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    # Referral info
    info_text += f"👥 **Запрошено друзів:** {referral_count}\n"
    
    # Statistics
    if stats_data:
        messages_sent, chats_count = stats_data
        info_text += f"\n📊 **Статистика активності:**\n"
        info_text += f"💬 **Повідомлень надіслано:** {messages_sent or 0}\n"
        info_text += f"🗣 **Чатів проведено:** {chats_count or 0}\n"
    
    await message.answer(info_text)

async def admin_set_pro(message: Message):
    """Admin command to set PRO status for user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/set_pro <user_id/username> <кількість> <одиниця>`\n\n"
            "**Одиниці часу:**\n"
            "• `m` - хвилини\n"
            "• `h` - години\n" 
            "• `d` - дні\n"
            "• `f` - назавжди\n\n"
            "**Приклади:**\n"
            "`/set_pro @username 15 m` - 15 хвилин\n"
            "`/set_pro 123456789 2 h` - 2 години\n"
            "`/set_pro @username 7 d` - 7 днів\n"
            "`/set_pro @username 1 f` - назавжди"
        )
        return
    
    if len(args) < 3:
        await message.answer("❌ Недостатньо аргументів. Використайте: `/set_pro <user> <кількість> <одиниця>`")
        return
    
    target_user = args[0]
    user_data = None
    
    # Check if it's username or user_id
    if target_user.startswith('@'):
        user_data = get_user_by_username(target_user)
    else:
        try:
            user_id = int(target_user)
            user_data = get_user_by_id(user_id)
        except ValueError:
            # Maybe it's username without @
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Parse duration
    try:
        amount = int(args[1])
        unit = args[2].lower()
    except ValueError:
        await message.answer("❌ Неправильний формат кількості. Використайте число.")
        return
    
    # Calculate total duration in seconds
    total_seconds = 0
    duration_text = ""
    
    if unit == 'f':  # forever
        total_seconds = 50 * 365 * 24 * 3600  # 50 years
        duration_text = "назавжди"
    elif unit == 'm':  # minutes
        total_seconds = amount * 60
        duration_text = f"{amount} хв."
    elif unit == 'h':  # hours
        total_seconds = amount * 3600
        duration_text = f"{amount} год."
    elif unit == 'd':  # days
        total_seconds = amount * 24 * 3600
        duration_text = f"{amount} дн."
    else:
        await message.answer("❌ Невідома одиниця часу. Використайте: m (хвилини), h (години), d (дні), f (назавжди)")
        return
    
    if total_seconds <= 0 and unit != 'f':
        await message.answer("❌ Тривалість PRO повинна бути більше 0.")
        return
    
    # Set PRO status using the pro_until field in users table
    import time
    current_time = int(time.time())
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current pro_until value
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_data['user_id'],))
    row = cur.fetchone()
    current_until = row[0] if row and row[0] else 0
    
    # Add time to current PRO or start from now
    new_until = max(current_time, current_until) + total_seconds
    
    # Update users table
    cur.execute('UPDATE users SET pro_until = ? WHERE user_id = ?', (new_until, user_data['user_id']))
    
    conn.commit()
    conn.close()
    
    # Format end date
    if unit == 'f':
        end_date_text = "Назавжди"
    else:
        end_date = datetime.fromtimestamp(new_until)
        end_date_text = end_date.strftime('%d.%m.%Y %H:%M')
    
    # Format user info
    user_info = f"ID: {user_data['user_id']}"
    if user_data['username']:
        user_info += f" (@{user_data['username']})"
    if user_data['first_name']:
        user_info += f" - {user_data['first_name']}"
    
    await message.answer(
        f"✅ **PRO статус надано!** 🌟\n\n"
        f"👤 **Користувач:** {user_info}\n"
        f"⏰ **Тривалість:** {duration_text}\n"
        f"📅 **До:** {end_date_text}"
    )

async def admin_remove_pro(message: Message):
    """Admin command to remove PRO status from user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/remove_pro <user_id>` - забрати PRO за ID\n"
            "`/remove_pro @username` - забрати PRO за username\n\n"
            "**Приклади:**\n"
            "`/remove_pro 123456789`\n"
            "`/remove_pro @username`"
        )
        return
    
    target_user = args[0]
    user_data = None
    
    # Check if it's username or user_id
    if target_user.startswith('@'):
        user_data = get_user_by_username(target_user)
    else:
        try:
            user_id = int(target_user)
            user_data = get_user_by_id(user_id)
        except ValueError:
            # Maybe it's username without @
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Remove PRO status
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if user has PRO
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_data['user_id'],))
    row = cur.fetchone()
    
    if not row or not row[0] or row[0] <= int(__import__('time').time()):
        await message.answer("❌ Користувач не має PRO статусу.")
        conn.close()
        return
    
    # Remove PRO by setting pro_until to 0
    cur.execute('UPDATE users SET pro_until = 0 WHERE user_id = ?', (user_data['user_id'],))
    conn.commit()
    conn.close()
    
    # Format user info
    user_info = f"ID: {user_data['user_id']}"
    if user_data['username']:
        user_info += f" (@{user_data['username']})"
    if user_data['first_name']:
        user_info += f" - {user_data['first_name']}"
    
    await message.answer(
        f"✅ **PRO статус забрано!** 🌟\n\n"
        f"👤 **Користувач:** {user_info}\n"
        f"📅 **Статус:** Звичайний користувач"
    )

def log_user_activity(user_id):
    """Log user activity for hourly statistics"""
    import time
    from datetime import datetime
    
    conn = get_conn()
    cur = conn.cursor()
    
    current_time = int(time.time())
    current_datetime = datetime.fromtimestamp(current_time)
    current_hour = current_datetime.hour
    current_date = current_datetime.strftime('%Y-%m-%d')
    
    # Check if activity already logged for this user in this hour
    cur.execute('''
    SELECT 1 FROM hourly_activity_stats 
    WHERE user_id = ? AND activity_hour = ? AND activity_date = ?
    ''', (user_id, current_hour, current_date))
    
    if not cur.fetchone():
        # Log new activity
        cur.execute('''
        INSERT INTO hourly_activity_stats (user_id, activity_hour, activity_date, activity_timestamp)
        VALUES (?, ?, ?, ?)
        ''', (user_id, current_hour, current_date, current_time))
        
        conn.commit()
    
    conn.close()

async def admin_stats_active_time(message: Message):
    """Admin command to get hourly activity statistics"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get today's date
    from datetime import datetime, timedelta
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Get hourly statistics for today
    cur.execute('''
    SELECT activity_hour, COUNT(DISTINCT user_id) as user_count
    FROM hourly_activity_stats 
    WHERE activity_date = ?
    GROUP BY activity_hour
    ORDER BY activity_hour
    ''', (str(today),))
    
    today_stats = dict(cur.fetchall())
    
    # Get hourly statistics for yesterday
    cur.execute('''
    SELECT activity_hour, COUNT(DISTINCT user_id) as user_count
    FROM hourly_activity_stats 
    WHERE activity_date = ?
    GROUP BY activity_hour
    ORDER BY activity_hour
    ''', (str(yesterday),))
    
    yesterday_stats = dict(cur.fetchall())
    
    # Get peak hour for today
    peak_hour_today = max(today_stats.items(), key=lambda x: x[1]) if today_stats else (0, 0)
    peak_hour_yesterday = max(yesterday_stats.items(), key=lambda x: x[1]) if yesterday_stats else (0, 0)
    
    conn.close()
    
    # Format response
    stats_text = f"📊 **Статистика активності по годинах**\n\n"
    
    # Today's stats
    stats_text += f"📅 **Сьогодні ({today.strftime('%d.%m.%Y')}):**\n"
    if today_stats:
        for hour in range(24):
            count = today_stats.get(hour, 0)
            if count > 0:
                stats_text += f"{hour:02d}:00-{hour+1:02d}:00 — {count} користувачів\n"
        
        stats_text += f"\n🔥 **Пік активності сьогодні:** {peak_hour_today[0]:02d}:00-{peak_hour_today[0]+1:02d}:00 ({peak_hour_today[1]} користувачів)\n"
    else:
        stats_text += "Немає даних за сьогодні\n"
    
    # Yesterday's stats
    stats_text += f"\n📅 **Вчора ({yesterday.strftime('%d.%m.%Y')}):**\n"
    if yesterday_stats:
        for hour in range(24):
            count = yesterday_stats.get(hour, 0)
            if count > 0:
                stats_text += f"{hour:02d}:00-{hour+1:02d}:00 — {count} користувачів\n"
        
        stats_text += f"\n🔥 **Пік активності вчора:** {peak_hour_yesterday[0]:02d}:00-{peak_hour_yesterday[0]+1:02d}:00 ({peak_hour_yesterday[1]} користувачів)\n"
    else:
        stats_text += "Немає даних за вчора\n"
    
    # Summary
    total_today = sum(today_stats.values()) if today_stats else 0
    total_yesterday = sum(yesterday_stats.values()) if yesterday_stats else 0
    
    stats_text += f"\n📈 **Підсумок:**\n"
    stats_text += f"• Всього активних сеансів сьогодні: {total_today}\n"
    stats_text += f"• Всього активних сеансів вчора: {total_yesterday}\n"
    
    if total_yesterday > 0:
        change_percent = ((total_today - total_yesterday) / total_yesterday) * 100
        change_emoji = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
        stats_text += f"• Зміна активності: {change_emoji} {change_percent:+.1f}%"
    
    await message.answer(stats_text)

async def admin_send_activity_notifications(message: Message):
    """Admin command to manually send activity notifications"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    try:
        # Parse command arguments
        command_parts = message.text.split()
        min_active_users = 10000  # Default value
        
        if len(command_parts) > 1:
            try:
                min_active_users = int(command_parts[1])
                if min_active_users < 0:
                    await message.answer("❌ Кількість активних користувачів не може бути від'ємною.")
                    return
            except ValueError:
                await message.answer("❌ Неправильний формат числа. Використовуйте: `/send_activity_notifications 10000`")
                return
        
        from activity_notifications import send_activity_notifications, get_current_activity_stats
        
        # Get current stats for info
        active_count, waiting_count = get_current_activity_stats()
        
        await send_activity_notifications(min_active_users)
        
        await message.answer(
            f"✅ **Сповіщення надіслано!**\n\n"
            f"📊 **Поточна статистика:**\n"
            f"• Активних користувачів: {active_count}\n"
            f"• Шукають співрозмовника: {waiting_count}\n"
            f"• Поріг для сповіщень: {min_active_users}\n\n"
            f"{'✅ Сповіщення надіслано' if active_count >= min_active_users else '❌ Недостатньо активності для сповіщень'}"
        )
        
    except Exception as e:
        await message.answer(f"❌ Помилка при надсиланні сповіщень: {e}")

async def admin_set_notification_threshold(message: Message):
    """Admin command to set notification threshold"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    try:
        # Parse command arguments
        command_parts = message.text.split()
        
        if len(command_parts) != 2:
            await message.answer(
                "❌ Неправильний формат команди.\n\n"
                "**Використання:** `/set_notification_threshold <кількість>`\n"
                "**Приклад:** `/set_notification_threshold 8000`"
            )
            return
        
        try:
            new_threshold = int(command_parts[1])
            if new_threshold < 0:
                await message.answer("❌ Поріг не може бути від'ємним.")
                return
        except ValueError:
            await message.answer("❌ Неправильний формат числа.")
            return
        
        # Set new threshold
        from activity_notifications import set_notification_threshold, get_notification_threshold
        
        old_threshold = get_notification_threshold()
        
        if set_notification_threshold(new_threshold):
            await message.answer(
                f"✅ **Поріг сповіщень оновлено!**\n\n"
                f"📊 **Зміни:**\n"
                f"• Старий поріг: {old_threshold}\n"
                f"• Новий поріг: {new_threshold}\n\n"
                f"🔔 Автоматичні сповіщення тепер надсилатимуться коли кількість активних користувачів досягне **{new_threshold}**"
            )
        else:
            await message.answer("❌ Помилка при збереженні нового порогу.")
        
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

async def admin_get_notification_settings(message: Message):
    """Admin command to get current notification settings"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    try:
        from activity_notifications import get_notification_threshold, get_current_activity_stats
        
        threshold = get_notification_threshold()
        active_count, waiting_count = get_current_activity_stats()
        
        # Calculate how close we are to threshold
        progress_percent = (active_count / threshold * 100) if threshold > 0 else 0
        
        settings_text = (
            f"⚙️ **Налаштування сповіщень**\n\n"
            f"🎯 **Поточний поріг:** {threshold} активних користувачів\n"
            f"👥 **Зараз активно:** {active_count} користувачів\n"
            f"🔍 **Шукають співрозмовника:** {waiting_count} осіб\n\n"
            f"📊 **Прогрес до порогу:** {progress_percent:.1f}%\n"
            f"{'🔔 Сповіщення будуть надіслані!' if active_count >= threshold else f'❌ До порогу залишилось: {threshold - active_count}'}\n\n"
            f"⏰ **Режим роботи:** Автоматична перевірка кожні 30 хвилин\n"
            f"📋 **Умови сповіщень:**\n"
            f"• Користувач неактивний 12+ годин\n"
            f"• Не отримував сповіщення сьогодні\n"
            f"• Активних користувачів ≥ {threshold}"
        )
        
        await message.answer(settings_text)
        
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

async def admin_block_user(message: Message):
    """Admin command to block user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    try:
        # Parse command arguments
        args = message.text.split()[1:]  # Remove command itself
        if len(args) < 1:
            await message.answer(
                "❌ **Неправильний формат команди!**\n\n"
                "📝 **Використання:**\n"
                "`/block_user <user_id/username> [причина]`\n\n"
                "📋 **Приклади:**\n"
                "• `/block_user 123456789 Спам`\n"
                "• `/block_user @username Порушення правил`\n"
                "• `/block_user 123456789` (без причини)"
            )
            return
        
        user_identifier = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Заблоковано адміністратором"
        
        # Find user
        if user_identifier.startswith('@'):
            user_data = get_user_by_username(user_identifier)
        elif user_identifier.isdigit():
            user_data = get_user_by_id(int(user_identifier))
        else:
            await message.answer("❌ Неправильний формат ID або username.")
            return
        
        if not user_data:
            await message.answer(f"❌ Користувача `{user_identifier}` не знайдено.")
            return
        
        user_id = user_data['user_id']
        
        # Check if user is already blocked
        from registration_aiogram import is_user_blocked
        if is_user_blocked(user_id):
            await message.answer(f"⚠️ Користувач `{user_identifier}` вже заблокований.")
            return
        
        # Block user
        from complaints_system import block_user
        block_user(user_id, message.from_user.id, reason)
        
        # Send notification to blocked user
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            from aiogram import Bot
            import os
            
            # Get bot token and create bot instance
            BOT_TOKEN = os.getenv('BOT_TOKEN')
            if BOT_TOKEN:
                bot_instance = Bot(token=BOT_TOKEN)
                
                # Create unblock button for 99 stars
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔓 Розблокувати за 99⭐", 
                            callback_data=f"unblock_pay_{user_id}"
                        )]
                    ]
                )
                
                block_message = (
                    f"🚫 **Ваш акаунт заблоковано**\n\n"
                    f"📋 **Причина:** {reason}\n"
                    f"👮‍♂️ **Заблокував:** Адміністратор\n\n"
                    f"💡 **Можливості:**\n"
                    f"• Зачекати розблокування адміністратором\n"
                    f"• Розблокувати негайно за 99⭐ (кнопка нижче)"
                )
                
                await bot_instance.send_message(
                    chat_id=user_id, 
                    text=block_message, 
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                await bot_instance.session.close()  # Close session after use
                print(f"Block notification sent to user {user_id} with unblock button")
            else:
                print("BOT_TOKEN not found in environment variables")
        except Exception as e:
            print(f"Error sending block notification: {e}")
        
        # Confirm to admin
        await message.answer(
            f"✅ **Користувача заблоковано!**\n\n"
            f"👤 **Користувач:** {user_data.get('first_name', 'N/A')} (@{user_data.get('username', 'N/A')})\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📋 **Причина:** {reason}\n"
            f"📧 **Повідомлення надіслано користувачу**"
        )
        
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

async def admin_unblock_user(message: Message):
    """Admin command to unblock user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    try:
        # Parse command arguments
        args = message.text.split()[1:]  # Remove command itself
        if len(args) < 1:
            await message.answer(
                "❌ **Неправильний формат команди!**\n\n"
                "📝 **Використання:**\n"
                "`/unblock_user <user_id/username>`\n\n"
                "📋 **Приклади:**\n"
                "• `/unblock_user 123456789`\n"
                "• `/unblock_user @username`"
            )
            return
        
        user_identifier = args[0]
        
        # Find user
        if user_identifier.startswith('@'):
            user_data = get_user_by_username(user_identifier)
        elif user_identifier.isdigit():
            user_data = get_user_by_id(int(user_identifier))
        else:
            await message.answer("❌ Неправильний формат ID або username.")
            return
        
        if not user_data:
            await message.answer(f"❌ Користувача `{user_identifier}` не знайдено.")
            return
        
        user_id = user_data['user_id']
        
        # Check if user is blocked
        from registration_aiogram import is_user_blocked
        if not is_user_blocked(user_id):
            await message.answer(f"⚠️ Користувач `{user_identifier}` не заблокований.")
            return
        
        # Unblock user
        from complaints_system import unblock_user
        unblock_user(user_id)
        
        # Send notification to unblocked user
        try:
            from aiogram import Bot
            import os
            
            # Get bot token and create bot instance
            BOT_TOKEN = os.getenv('BOT_TOKEN')
            if BOT_TOKEN:
                bot_instance = Bot(token=BOT_TOKEN)
                
                unblock_message = (
                    f"✅ **Ваш акаунт розблоковано!**\n\n"
                    f"🎉 **Доброго повернення!**\n"
                    f"👮‍♂️ **Розблокував:** Адміністратор\n\n"
                    f"💡 **Нагадування:**\n"
                    f"• Дотримуйтесь правил спільноти\n"
                    f"• Будьте ввічливими з іншими користувачами\n\n"
                    f"🚀 **Можете продовжувати користуватися ботом!**"
                )
                
                await bot_instance.send_message(
                    chat_id=user_id, 
                    text=unblock_message,
                    parse_mode="Markdown"
                )
                await bot_instance.session.close()  # Close session after use
            else:
                print("BOT_TOKEN not found in environment variables")
        except Exception as e:
            print(f"Error sending unblock notification: {e}")
        
        # Confirm to admin
        await message.answer(
            f"✅ **Користувача розблоковано!**\n\n"
            f"👤 **Користувач:** {user_data.get('first_name', 'N/A')} (@{user_data.get('username', 'N/A')})\n"
        )
    
    except Exception as e:
        await message.answer(f"❌ Помилка при розблокуванні користувача: {e}")

# Global dictionary to store admin following sessions
admin_following = {}

async def admin_follow_user(message: Message):
    """Admin command to start following a user's conversations"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    admin_id = message.from_user.id
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer("❌ Вкажіть ID або username користувача.\nВикористання: `/follow <user_id/username>`")
        return
    
    target_identifier = args[0]
    
    # Find user by ID or username
    from registration_aiogram import get_user_by_username, get_user
    
    target_user_id = None
    if target_identifier.startswith('@'):
        username = target_identifier[1:]
        user_data = get_user_by_username(username)
        if user_data:
            target_user_id = user_data['user_id']
    else:
        try:
            target_user_id = int(target_identifier)
            user_data = get_user(target_user_id)
            if not user_data:
                target_user_id = None
        except ValueError:
            pass
    
    if not target_user_id:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    # Check if admin is already following someone
    if admin_id in admin_following:
        current_target = admin_following[admin_id]
        await message.answer(f"⚠️ Ви вже стежите за користувачем {current_target}.\nВикористайте /unfollow щоб припинити стеження.")
        return
    
    # Start following
    admin_following[admin_id] = target_user_id
    user_data = get_user(target_user_id)
    
    await message.answer(
        f"👁️ **Розпочато стеження за користувачем:**\n\n"
        f"🆔 ID: `{target_user_id}`\n"
        f"👤 Ім'я: {user_data.get('first_name', 'Невідомо')}\n"
        f"📝 Username: @{user_data.get('username', 'немає')}\n\n"
        f"📡 Тепер ви будете бачити всі повідомлення цього користувача в реальному часі.\n"
        f"🛑 Щоб припинити стеження, використайте /unfollow"
    )

async def admin_unfollow_user(message: Message):
    """Admin command to stop following a user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    
    admin_id = message.from_user.id
    
    if admin_id not in admin_following:
        await message.answer("❌ Ви зараз ні за ким не стежите.")
        return
    
    target_user_id = admin_following[admin_id]
    del admin_following[admin_id]
    
    from registration_aiogram import get_user
    user_data = get_user(target_user_id)
    
    await message.answer(
        f"🛑 **Стеження припинено:**\n\n"
        f"🆔 ID: `{target_user_id}`\n"
        f"👤 Ім'я: {user_data.get('first_name', 'Невідомо')}\n\n"
        f"✅ Ви більше не отримуватимете повідомлення цього користувача."
    )

async def send_message_to_following_admins(user_id, message_text, message_type="text", media_info=None, is_receiver=False):
    """Send message copy to admins who are following this user"""
    if not admin_following:
        return
    
    # Find admins following this user
    following_admins = [admin_id for admin_id, target_id in admin_following.items() if target_id == user_id]
    
    if not following_admins:
        return
    
    from registration_aiogram import get_user
    from chat_aiogram import get_partner
    
    user_data = get_user(user_id)
    partner_id = get_partner(user_id)
    partner_data = get_user(partner_id) if partner_id else None
    
    # Create header based on whether this is sender or receiver
    if is_receiver:
        # This is the partner receiving the message, show as "Інкогніто"
        header = f"👁️ Інкогніто: "
    else:
        # This is the followed user sending the message
        sender_name = user_data.get('first_name', 'Невідомо')
        header = f"👁️ {sender_name}: "
    
    # Send to all following admins
    from bot_aiogram import bot
    for admin_id in following_admins:
        try:
            if message_type == "text":
                full_message = f"{header}{message_text}"
                await bot.send_message(admin_id, full_message)
            elif message_type == "photo" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_photo(admin_id, media_info, caption=caption)
            elif message_type == "video" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_video(admin_id, media_info, caption=caption)
            elif message_type == "voice" and media_info:
                await bot.send_voice(admin_id, media_info, caption=header)
            elif message_type == "document" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_document(admin_id, media_info, caption=caption)
            elif message_type == "sticker" and media_info:
                await bot.send_sticker(admin_id, media_info)
            elif message_type == "animation" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_animation(admin_id, media_info, caption=caption)
                
        except Exception as e:
            print(f"Error sending follow message to admin {admin_id}: {e}")

async def send_message_to_following_admins_conversation(sender_id, receiver_id, message_text, message_type="text", media_info=None):
    """Send message copy to admins who are following either user in the conversation"""
    if not admin_following:
        return
    
    # Find admins following either user
    following_admins = []
    followed_user_id = None
    
    for admin_id, target_id in admin_following.items():
        if target_id == sender_id:
            following_admins.append(admin_id)
            followed_user_id = sender_id
        elif target_id == receiver_id:
            following_admins.append(admin_id)
            followed_user_id = receiver_id
    
    if not following_admins:
        return
    
    from registration_aiogram import get_user
    
    sender_data = get_user(sender_id)
    receiver_data = get_user(receiver_id)
    
    # Determine who is the followed user and who is "Інкогніто"
    if followed_user_id == sender_id:
        # Admin is following the sender
        sender_name = sender_data.get('first_name', 'Невідомо')
        header = f"👁️ {sender_name}: "
    else:
        # Admin is following the receiver, so sender is "Інкогніто"
        header = f"👁️ Інкогніто: "
    
    # Send to all following admins
    from bot_aiogram import bot
    for admin_id in following_admins:
        try:
            if message_type == "text":
                full_message = f"{header}{message_text}"
                await bot.send_message(admin_id, full_message)
            elif message_type == "photo" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_photo(admin_id, media_info, caption=caption)
            elif message_type == "video" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_video(admin_id, media_info, caption=caption)
            elif message_type == "voice" and media_info:
                await bot.send_voice(admin_id, media_info, caption=header)
            elif message_type == "document" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_document(admin_id, media_info, caption=caption)
            elif message_type == "sticker" and media_info:
                await bot.send_sticker(admin_id, media_info)
            elif message_type == "animation" and media_info:
                caption = f"{header}{message_text}" if message_text else header
                await bot.send_animation(admin_id, media_info, caption=caption)
                
        except Exception as e:
            print(f"Error sending follow message to admin {admin_id}: {e}")

def register_admin_handlers(dp):
    """Register admin command handlers"""
    dp.message.register(admin_set_premium, Command("set_premium"))
    dp.message.register(admin_remove_premium, Command("remove_premium"))
    dp.message.register(admin_set_pro, Command("set_pro"))
    dp.message.register(admin_remove_pro, Command("remove_pro"))
    dp.message.register(admin_stats, Command("admin_stats"))
    dp.message.register(admin_user_info, Command("user_info"))
    dp.message.register(admin_stats_active_time, Command("stats_aktive_time"))
    dp.message.register(admin_send_activity_notifications, Command("send_activity_notifications"))
    dp.message.register(admin_set_notification_threshold, Command("set_notification_threshold"))
    dp.message.register(admin_get_notification_settings, Command("notification_settings"))
    dp.message.register(admin_block_user, Command("block_user"))
    dp.message.register(admin_unblock_user, Command("unblock_user"))
    dp.message.register(admin_follow_user, Command("follow"))
    dp.message.register(admin_unfollow_user, Command("unfollow"))
    dp.message.register(admin_maintenance_on, Command("maintenance_on"))
    dp.message.register(admin_maintenance_off, Command("maintenance_off"))

async def admin_maintenance_on(message: Message):
    """Enable maintenance mode. Optional text after command is a custom banner."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    parts = message.text.split(maxsplit=1)
    custom_text = parts[1] if len(parts) > 1 else None
    try:
        enable_maintenance(custom_text)
        banner = custom_text or "🔧 Технічна перерва. Пошук тимчасово недоступний."
        await message.answer(f"✅ Режим технічної перерви увімкнено.\n\nПовідомлення для користувачів:\n{banner}")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

async def admin_maintenance_off(message: Message):
    """Disable maintenance mode and notify that search works."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    try:
        disable_maintenance()
        await message.answer("✅ Режим технічної перерви вимкнено. Пошук знову доступний.")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")
