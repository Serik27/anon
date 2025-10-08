import sqlite3
import time
from datetime import datetime
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Import from existing modules
from registration_aiogram import get_conn, get_user
from premium_aiogram import is_pro, get_user_status

# States for adding friends
class FriendStates(StatesGroup):
    waiting_for_name = State()

def init_friends_tables():
    """Initialize friends-related database tables"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Create chat_requests table for PRO user requests
    cur.execute('''
    CREATE TABLE IF NOT EXISTS chat_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER NOT NULL,
        to_user_id INTEGER NOT NULL,
        request_time INTEGER DEFAULT (strftime('%s', 'now')),
        status TEXT DEFAULT 'pending',
        UNIQUE(from_user_id, to_user_id)
    )
    ''')
    
    # Create return_requests table for return to partner functionality
    cur.execute('''
    CREATE TABLE IF NOT EXISTS return_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER NOT NULL,
        to_user_id INTEGER NOT NULL,
        request_time INTEGER DEFAULT (strftime('%s', 'now')),
        status TEXT DEFAULT 'waiting',
        UNIQUE(from_user_id, to_user_id)
    )
    ''')
    
    # Create activity_notifications table for friend activity notifications
    cur.execute('''
    CREATE TABLE IF NOT EXISTS activity_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        enabled INTEGER DEFAULT 0,
        UNIQUE(user_id, friend_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def update_user_activity(user_id, is_chatting=False):
    """Update user activity timestamp"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get previous activity status
    cur.execute('SELECT is_chatting FROM user_activity WHERE user_id = ?', (user_id,))
    prev_row = cur.fetchone()
    prev_is_chatting = bool(prev_row[0]) if prev_row else False
    
    current_time = int(time.time())
    cur.execute('''
    INSERT OR REPLACE INTO user_activity (user_id, last_activity, is_chatting)
    VALUES (?, ?, ?)
    ''', (user_id, current_time, 1 if is_chatting else 0))
    
    conn.commit()
    conn.close()
    
    # Send notifications if activity status changed
    if is_chatting != prev_is_chatting:
        import asyncio
        asyncio.create_task(send_activity_notifications(user_id, is_chatting))

async def send_activity_notifications(user_id, is_chatting):
    """Send activity notifications to users who subscribed"""
    try:
        # Get users who have notifications enabled for this friend
        users_to_notify = get_users_with_notifications_for_friend(user_id)
        
        if not users_to_notify:
            return
        
        # Get user info
        user_data = get_user(user_id)
        if not user_data:
            return
        
        # Create notification message
        if is_chatting:
            message = f"🤖 Ваш друг {user_data.get('first_name', 'Невідомо')} зараз активний в боті"
        else:
            message = f"😴 Ваш друг {user_data.get('first_name', 'Невідомо')} більше не активний в боті"
        
        # Send notifications
        from bot_aiogram import bot
        for notify_user_id in users_to_notify:
            try:
                await bot.send_message(notify_user_id, message)
            except Exception as e:
                print(f"Error sending activity notification to {notify_user_id}: {e}")
                
    except Exception as e:
        print(f"Error in send_activity_notifications: {e}")

def get_user_activity(user_id):
    """Get user activity info"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT last_activity, is_chatting FROM user_activity WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        last_activity, is_chatting = row
        current_time = int(time.time())
        
        # Online if active in last 5 minutes
        is_online = (current_time - last_activity) < 300
        # Active in bot if active in last minute
        is_bot_active = (current_time - last_activity) < 60
        
        return {
            'is_online': is_online,
            'is_chatting': bool(is_chatting),
            'is_bot_active': is_bot_active,
            'last_activity': last_activity
        }
    
    return {
        'is_online': False,
        'is_chatting': False,
        'is_bot_active': False,
        'last_activity': 0
    }

def add_friend(user_id, friend_id, friend_name):
    """Add friend to user's friend list"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if already friends
    cur.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
    if cur.fetchone():
        conn.close()
        return False, "Користувач вже у списку друзів"
    
    # Add friend
    cur.execute('''
    INSERT INTO friends (user_id, friend_id, friend_name, added_date)
    VALUES (?, ?, ?, ?)
    ''', (user_id, friend_id, friend_name, int(time.time())))
    
    conn.commit()
    conn.close()
    return True, "Друга додано успішно"

def get_friends_list(user_id, page=0, per_page=7):
    """Get user's friends list with pagination"""
    conn = get_conn()
    cur = conn.cursor()
    
    offset = page * per_page
    cur.execute('''
    SELECT friend_id, friend_name, added_date 
    FROM friends 
    WHERE user_id = ? 
    ORDER BY added_date DESC 
    LIMIT ? OFFSET ?
    ''', (user_id, per_page, offset))
    
    friends = cur.fetchall()
    
    # Get total count
    cur.execute('SELECT COUNT(*) FROM friends WHERE user_id = ?', (user_id,))
    total_count = cur.fetchone()[0]
    
    conn.close()
    
    return friends, total_count

def get_friend_info(user_id, friend_id):
    """Get detailed friend information"""
    # Get basic user info
    user_data = get_user(friend_id)
    if not user_data:
        return None
    
    # Get activity info
    activity = get_user_activity(friend_id)
    
    # Get ratings
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT rating_type, count 
    FROM ratings 
    WHERE user_id = ?
    ''', (friend_id,))
    ratings = dict(cur.fetchall())
    
    conn.close()
    
    return {
        'user_data': user_data,
        'activity': activity,
        'ratings': ratings
    }

def create_friends_keyboard(friends, page=0, total_count=0, per_page=7):
    """Create inline keyboard for friends list"""
    keyboard = []
    
    # Add friend buttons
    for friend_id, friend_name, _ in friends:
        keyboard.append([InlineKeyboardButton(
            text=friend_name, 
            callback_data=f"friend_info_{friend_id}"
        )])
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data=f"friends_page_{page-1}"
        ))
    
    if (page + 1) * per_page < total_count:
        nav_buttons.append(InlineKeyboardButton(
            text="Далі ➡️", 
            callback_data=f"friends_page_{page+1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="friends_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_friend_info_keyboard(friend_id, user_id=None):
    """Create keyboard for friend info with action buttons"""
    keyboard = [
        [InlineKeyboardButton(text="📞 Запрос", callback_data=f"friend_request_{friend_id}")],
    ]
    
    # Check if friend has anonymous mode enabled
    if not is_pro_anonymous(friend_id):
        keyboard.append([InlineKeyboardButton(text="👤 Отримати аккаунт", callback_data=f"friend_account_{friend_id}")])
        
        # Get notification status if user_id provided
        notification_text = "🔔 Повідомлення про активність"
        if user_id:
            is_enabled = get_activity_notification_status(user_id, friend_id)
            notification_text = f"🔔{'✅' if is_enabled else '❌'} Повідомлення про активність"
        
        keyboard.append([InlineKeyboardButton(text=notification_text, callback_data=f"friend_activity_{friend_id}")])
    
    # Add delete friend button
    keyboard.append([InlineKeyboardButton(text="🗑️ Видалити друга", callback_data=f"friend_delete_{friend_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад до списку", callback_data="friends_list")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def delete_friend(user_id, friend_id):
    """Delete friend from user's friends list"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Delete from friends table
        cur.execute('DELETE FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
        
        # Also delete activity notifications for this friend
        cur.execute('DELETE FROM activity_notifications WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        conn.close()
        return False

def get_friend_name(user_id, friend_id):
    """Get friend's display name"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get custom name from friends table
        cur.execute('SELECT friend_name FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
        result = cur.fetchone()
        
        if result and result[0]:
            conn.close()
            return result[0]
        
        # If no custom name, get user's first name or username
        user_data = get_user(friend_id)
        if user_data:
            name = user_data.get('first_name') or user_data.get('username') or f"User {friend_id}"
            conn.close()
            return name
        
        conn.close()
        return f"User {friend_id}"
        
    except Exception as e:
        conn.close()
        return f"User {friend_id}"

async def show_friends_list(message_or_callback, page=0):
    """Show friends list"""
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
        message = message_or_callback.message
        is_callback = True
    else:
        user_id = message_or_callback.from_user.id
        message = message_or_callback
        is_callback = False
    
    # Check PRO status
    if not is_pro(user_id):
        text = "❌ Ця функція доступна тільки PRO користувачам!"
        if is_callback:
            await message_or_callback.answer(text, show_alert=True)
        else:
            await message.answer(text)
        return
    
    # Get friends list
    friends, total_count = get_friends_list(user_id, page)
    
    if not friends:
        text = "👥 **Список друзів порожній**\n\nВикористайте команду `/add_friends` або кнопку 'Додати в друзі' після розмови, щоб додати друзів."
        keyboard = None
    else:
        text = f"👥 **Ваші друзі** (сторінка {page + 1})\n\nВиберіть друга для перегляду детальної інформації:"
        keyboard = create_friends_keyboard(friends, page, total_count)
    
    if is_callback:
        await message.edit_text(text, reply_markup=keyboard)
        await message_or_callback.answer()
    else:
        await message.answer(text, reply_markup=keyboard)

async def show_friend_info(callback: types.CallbackQuery, friend_id: int):
    """Show detailed friend information"""
    user_id = callback.from_user.id
    
    # Check PRO status
    if not is_pro(user_id):
        await callback.answer("❌ Ця функція доступна тільки PRO користувачам!", show_alert=True)
        return
    
    # Get friend info
    friend_info = get_friend_info(user_id, friend_id)
    if not friend_info:
        await callback.answer("❌ Друга не знайдено", show_alert=True)
        return
    
    user_data = friend_info['user_data']
    activity = friend_info['activity']
    ratings = friend_info['ratings']
    
    # Check if friend has anonymous mode enabled
    is_anonymous = is_pro_anonymous(friend_id)
    
    # Format info text
    text = f"👤 *Інформація про друга*\n\n"
    text += f"🆔 *ID:* {user_data['user_id']}\n"
    
    if not is_anonymous and user_data.get('username'):
        text += f"📝 *Username:* @{user_data['username']}\n"
    elif is_anonymous:
        text += f"🔒 *Username:* Приховано (анонімний режим)\n"
    
    if user_data.get('gender'):
        text += f"⚧ *Стать:* {user_data['gender']}\n"
    
    if user_data.get('age'):
        text += f"🎂 *Вік:* {user_data['age']}\n"
    
    if user_data.get('country'):
        text += f"🌍 *Країна:* {user_data['country']}\n"
    
    # Check if user is blocked
    from complaints_system import is_user_blocked
    if is_user_blocked(friend_id):
        text += f"🚫 *Статус:* Заблокований\n"
    else:
        text += f"✅ *Статус:* Активний\n"
    
    # Activity status - hide if anonymous
    if not is_anonymous:
        text += f"\n📊 *Статус активності:*\n"
        
        # Telegram online status (based on last activity in last 5 minutes)
        if activity['is_online']:
            text += f"🟢 *Онлайн в Telegram*\n"
        else:
            text += f"🔴 *Офлайн в Telegram*\n"
        
        # Bot activity status
        if activity['is_chatting']:
            text += f"💬 *Спілкується в боті зараз*\n"
        elif activity['is_bot_active']:
            text += f"🤖 *Активний в боті* (останні хвилини)\n"
        else:
            text += f"😴 *Неактивний в боті*\n"
    else:
        text += f"\n🔒 *Статус активності:* Приховано (анонімний режим)\n"
    
    # Ratings - always show section
    text += f"\n⭐ *Реакції:*\n"
    good_count = ratings.get('good', 0) if ratings else 0
    bad_count = ratings.get('bad', 0) if ratings else 0
    super_count = ratings.get('super', 0) if ratings else 0
    
    # Always show all reaction types with counts (even if 0)
    text += f"👍 Добре: {good_count}\n"
    text += f"👎 Погано: {bad_count}\n"
    text += f"❤️ Супер: {super_count}\n"
    
    keyboard = create_friend_info_keyboard(friend_id, user_id)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def handle_add_friends_command(message: types.Message, state: FSMContext):
    """Handle /add_friends command"""
    user_id = message.from_user.id
    
    # Check PRO status
    if not is_pro(user_id):
        await message.answer("❌ Ця функція доступна тільки PRO користувачам!")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📋 **Використання команди:**\n\n"
            "`/add_friends <user_id>` - додати за ID\n"
            "`/add_friends @username` - додати за username\n\n"
            "**Приклади:**\n"
            "`/add_friends 123456789`\n"
            "`/add_friends @username`"
        )
        return
    
    target_user = args[0]
    
    # Find user
    if target_user.startswith('@'):
        from admin_commands import get_user_by_username
        user_data = get_user_by_username(target_user)
    else:
        try:
            friend_id = int(target_user)
            from admin_commands import get_user_by_id
            user_data = get_user_by_id(friend_id)
        except ValueError:
            from admin_commands import get_user_by_username
            user_data = get_user_by_username(target_user)
    
    if not user_data:
        await message.answer("❌ Користувача не знайдено.")
        return
    
    if user_data['user_id'] == user_id:
        await message.answer("❌ Ви не можете додати себе в друзі.")
        return
    
    # Ask for friend name
    await message.answer(
        f"👤 **Додавання в друзі**\n\n"
        f"Користувач: {user_data.get('first_name', 'Невідомо')} "
        f"(@{user_data.get('username', 'немає')})\n\n"
        f"Введіть ім'я для цього друга:"
    )
    
    # Store friend_id in state and set FSM state
    await state.update_data(adding_friend_id=user_data['user_id'])
    
    # Import FriendStates from the main bot file
    from bot_aiogram import FriendStates
    await state.set_state(FriendStates.waiting_for_name)
    
    # Log state setting for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Set state FriendStates.waiting_for_name for user {user_id} via /add_friends command, friend_id: {user_data['user_id']}")

def create_chat_request(from_user_id, to_user_id):
    """Create a chat request from PRO user to another user"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('''
        INSERT INTO chat_requests (from_user_id, to_user_id)
        VALUES (?, ?)
        ''', (from_user_id, to_user_id))
        conn.commit()
        conn.close()
        return True, "Запрос відправлено"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Запрос вже існує"

def get_pending_request_for_user(user_id):
    """Get pending chat request for user (when they start searching)"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT from_user_id, request_time 
    FROM chat_requests 
    WHERE to_user_id = ? AND status = 'pending'
    ORDER BY request_time ASC
    LIMIT 1
    ''', (user_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return row[0]  # Return from_user_id
    return None

def accept_chat_request(from_user_id, to_user_id):
    """Accept chat request and mark as accepted"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    UPDATE chat_requests 
    SET status = 'accepted'
    WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
    ''', (from_user_id, to_user_id))
    
    conn.commit()
    conn.close()

def reject_chat_request(from_user_id, to_user_id):
    """Reject chat request"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    UPDATE chat_requests 
    SET status = 'rejected'
    WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
    ''', (from_user_id, to_user_id))
    
    conn.commit()
    conn.close()

def create_return_request(from_user_id, to_user_id):
    """Create a return request from premium/pro user to previous partner"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('''
        INSERT OR REPLACE INTO return_requests (from_user_id, to_user_id)
        VALUES (?, ?)
        ''', (from_user_id, to_user_id))
        conn.commit()
        conn.close()
        return True, "Запрос на повернення створено"
    except Exception as e:
        conn.close()
        return False, f"Помилка: {e}"

def get_pending_return_request_for_user(user_id):
    """Get pending return request for user (when they start searching)"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT from_user_id, request_time 
    FROM return_requests 
    WHERE to_user_id = ? AND status = 'waiting'
    ORDER BY request_time ASC
    LIMIT 1
    ''', (user_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return row[0]  # Return from_user_id
    return None

def cancel_return_request(user_id):
    """Cancel return request for user"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    UPDATE return_requests 
    SET status = 'cancelled'
    WHERE from_user_id = ? AND status = 'waiting'
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def has_pending_return_request(user_id):
    """Check if user has pending return request"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT COUNT(*) FROM return_requests 
    WHERE from_user_id = ? AND status = 'waiting'
    ''', (user_id,))
    
    count = cur.fetchone()[0]
    conn.close()
    
    return count > 0

def accept_return_request(from_user_id, to_user_id):
    """Accept return request and mark as accepted"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    UPDATE return_requests 
    SET status = 'accepted'
    WHERE from_user_id = ? AND to_user_id = ? AND status = 'waiting'
    ''', (from_user_id, to_user_id))
    
    conn.commit()
    conn.close()

def toggle_activity_notification(user_id, friend_id):
    """Toggle activity notification for a friend"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check current status
    cur.execute('''
    SELECT enabled FROM activity_notifications 
    WHERE user_id = ? AND friend_id = ?
    ''', (user_id, friend_id))
    
    row = cur.fetchone()
    if row:
        # Toggle existing setting
        new_status = 0 if row[0] else 1
        cur.execute('''
        UPDATE activity_notifications 
        SET enabled = ?
        WHERE user_id = ? AND friend_id = ?
        ''', (new_status, user_id, friend_id))
    else:
        # Create new notification setting (enabled by default when first toggled)
        new_status = 1
        cur.execute('''
        INSERT INTO activity_notifications (user_id, friend_id, enabled)
        VALUES (?, ?, ?)
        ''', (user_id, friend_id, new_status))
    
    conn.commit()
    conn.close()
    
    return bool(new_status)

def get_activity_notification_status(user_id, friend_id):
    """Get activity notification status for a friend"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT enabled FROM activity_notifications 
    WHERE user_id = ? AND friend_id = ?
    ''', (user_id, friend_id))
    
    row = cur.fetchone()
    conn.close()
    
    return bool(row[0]) if row else False

def get_users_with_notifications_for_friend(friend_id):
    """Get list of users who have notifications enabled for this friend"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT user_id FROM activity_notifications 
    WHERE friend_id = ? AND enabled = 1
    ''', (friend_id,))
    
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    
    return users

def is_pro_anonymous(user_id):
    """Check if PRO user has anonymous mode enabled"""
    if not is_pro(user_id):
        return False
        
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT pro_anonymous FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        conn.close()
        
        return bool(row[0]) if row and row[0] is not None else False
    except Exception:
        conn.close()
        return False

def toggle_pro_anonymous(user_id):
    """Toggle PRO anonymous mode for user"""
    if not is_pro(user_id):
        return False, "Ця функція доступна тільки PRO користувачам"
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get current status
        cur.execute('SELECT pro_anonymous FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        current_status = bool(row[0]) if row and row[0] is not None else False
        
        # Toggle status
        new_status = not current_status
        cur.execute('UPDATE users SET pro_anonymous = ? WHERE user_id = ?', (int(new_status), user_id))
        
        conn.commit()
        conn.close()
        
        return True, new_status
    except Exception as e:
        conn.close()
        return False, f"Помилка: {e}"

async def handle_friends_command(message: types.Message):
    """Handle /friends command"""
    await show_friends_list(message)

# Initialize friends tables when module is imported
init_friends_tables()
