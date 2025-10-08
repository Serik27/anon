import asyncio
import logging
import os
import sqlite3
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from registration_aiogram import get_conn
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration from .env
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '8498395776'))
MAIN_BOT_USERNAME = "@YourMainBotUsername"  # Username основного бота

if not ADMIN_BOT_TOKEN:
    raise ValueError("ADMIN_BOT_TOKEN not found in .env file")

# Initialize bot and dispatcher
admin_bot = Bot(
    token=ADMIN_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

# Admin IDs - користувач з .env файлу
ADMIN_IDS = [ADMIN_USER_ID]

# States for admin actions
class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()
    waiting_for_channel_url = State()
    waiting_for_channel_name = State()
    # Advertisement states
    waiting_for_ad_name = State()
    waiting_for_ad_media = State()
    waiting_for_ad_message = State()
    waiting_for_button_name = State()
    waiting_for_button_url = State()
    waiting_for_ad_audience = State()
    confirming_ad = State()

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def get_user_info_for_admin(user_id):
    """Get detailed user information for admin"""
    from registration_aiogram import get_user
    from user_profile_aiogram import get_user_ratings
    from premium_aiogram import is_premium, is_pro
    
    user_data = get_user(user_id)
    if not user_data:
        return None
    
    # Get ratings
    ratings = get_user_ratings(user_id)
    
    # Get user status
    status = "👤 Звичайний"
    if is_pro(user_id):
        status = "🌟 PRO"
    elif is_premium(user_id):
        status = "💎 Premium"
    
    # Get chat statistics
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT messages_sent, chats_count FROM statistics WHERE user_id = ?', (user_id,))
    stats = cur.fetchone()
    messages_sent = stats[0] if stats else 0
    chats_count = stats[1] if stats else 0
    
    conn.close()
    
    return {
        'user_id': user_data['user_id'],
        'username': user_data.get('username'),
        'first_name': user_data.get('first_name'),
        'gender': user_data.get('gender'),
        'age': user_data.get('age'),
        'country': user_data.get('country'),
        'registration_date': user_data.get('registration_date'),
        'status': status,
        'ratings': ratings,
        'messages_sent': messages_sent,
        'chats_count': chats_count
    }

def migrate_complaints_table(cur, conn):
    """Migrate old complaints table schema to new one"""
    logger.info("Migrating complaints table schema...")
    
    try:
        # Create new table with correct schema
        cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL,
            reported_user_id INTEGER NOT NULL,
            reason TEXT,
            timestamp INTEGER DEFAULT (strftime('%s', 'now')),
            status TEXT DEFAULT 'pending',
            admin_response TEXT,
            response_date INTEGER
        )
        ''')
        
        # Copy data from old table to new table, mapping columns
        cur.execute('''
        INSERT INTO complaints_new (id, reporter_id, reported_user_id, reason, timestamp, status, admin_response, response_date)
        SELECT id, 
               COALESCE(complainant_id, reporter_id) as reporter_id,
               reported_user_id,
               COALESCE(complaint_text, reason) as reason,
               COALESCE(complaint_date, timestamp, strftime('%s', 'now')) as timestamp,
               status,
               admin_response,
               response_date
        FROM complaints
        ''')
        
        # Drop old table and rename new one
        cur.execute('DROP TABLE complaints')
        cur.execute('ALTER TABLE complaints_new RENAME TO complaints')
        
        conn.commit()
        logger.info("Complaints table migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during complaints table migration: {e}")
        conn.rollback()

def init_admin_tables():
    """Initialize admin-related database tables"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if complaints table exists and has wrong schema
    try:
        cur.execute("SELECT complainant_id FROM complaints LIMIT 1")
        # If this succeeds, we have the old schema - need to migrate
        migrate_complaints_table(cur, conn)
    except sqlite3.OperationalError:
        # Table doesn't exist or doesn't have complainant_id column - this is good
        pass
    
    # Create complaints table (matches complaints_system.py schema)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL,
        reported_user_id INTEGER NOT NULL,
        reason TEXT,
        timestamp INTEGER DEFAULT (strftime('%s', 'now')),
        status TEXT DEFAULT 'pending',
        admin_response TEXT,
        response_date INTEGER,
        rejected_count INTEGER DEFAULT 0
    )
    ''')
    
    # Add missing columns to complaints table if they don't exist
    try:
        cur.execute('ALTER TABLE complaints ADD COLUMN rejected_count INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute('ALTER TABLE complaints ADD COLUMN admin_response TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute('ALTER TABLE complaints ADD COLUMN response_date INTEGER')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create table for storing user conversations
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        partner_id INTEGER NOT NULL,
        conversation_data TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create table for blocked users
    cur.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY,
        blocked_by INTEGER NOT NULL,
        reason TEXT,
        timestamp INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Add missing columns to blocked_users table if they don't exist
    try:
        cur.execute('ALTER TABLE blocked_users ADD COLUMN blocked_by INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute('ALTER TABLE blocked_users ADD COLUMN reason TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute('ALTER TABLE blocked_users ADD COLUMN timestamp INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create broadcast_messages table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS broadcast_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_text TEXT,
        sent_date INTEGER,
        sent_by INTEGER,
        total_users INTEGER,
        successful_sends INTEGER
    )
    ''')
    
    # Create required_channels table
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
    
    conn.commit()
    conn.close()

@dp.message(Command("start"))
async def start_admin_command(message: Message):
    """Start command for admin bot"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цього бота.")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скарги", callback_data="admin_complaints")],
            [InlineKeyboardButton(text="🎯 Реклама", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📺 Канали", callback_data="admin_channels")]
        ]
    )
    
    await message.answer(
        f"🔧 **Адміністративна панель**\n\n"
        f"Керування ботом {MAIN_BOT_USERNAME}\n\n"
        f"Виберіть дію:",
        reply_markup=keyboard
    )

@dp.callback_query()
async def handle_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle admin callback queries"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ заборонено", show_alert=True)
        return
    
    if callback.data == "admin_complaints":
        await show_complaints(callback)
    elif callback.data == "admin_broadcast":
        await show_broadcast_menu(callback)
    elif callback.data == "admin_channels":
        await show_channels_menu(callback)
    elif callback.data == "create_ad":
        await create_ad(callback, state)
    elif callback.data == "active_ads":
        await show_active_ads(callback)
    elif callback.data.startswith("complaint_user_"):
        if "_delete_" in callback.data:
            # Handle return from conversations with message deletion
            parts = callback.data.split("_delete_")
            user_id = int(parts[0].replace("complaint_user_", ""))
            message_ids = parts[1].split(",")
            
            # Delete conversation messages
            for msg_id in message_ids:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, int(msg_id))
                except Exception as e:
                    print(f"Error deleting message {msg_id}: {e}")
            
            await show_complaint_user_details_new(callback, user_id)
        else:
            user_id = int(callback.data.replace("complaint_user_", ""))
            await show_complaint_user_details(callback, user_id)
    elif callback.data.startswith("complaint_block_"):
        user_id = int(callback.data.replace("complaint_block_", ""))
        await block_user_from_complaints(callback, user_id)
    elif callback.data.startswith("complaint_dismiss_"):
        user_id = int(callback.data.replace("complaint_dismiss_", ""))
        await dismiss_user_complaints(callback, user_id)
    elif callback.data.startswith("complaint_conversations_"):
        user_id = int(callback.data.replace("complaint_conversations_", ""))
        await show_user_conversations(callback, user_id)
    elif callback.data.startswith("complaint_"):
        await handle_complaint_action(callback)
    elif callback.data.startswith("channel_"):
        await handle_channel_action(callback, state)
    elif callback.data.startswith("delete_ad_"):
        await delete_ad(callback)
    elif callback.data.startswith("view_ad_"):
        await view_ad(callback)
    elif callback.data == "skip_media":
        await skip_media(callback, state)
    elif callback.data == "add_button":
        await add_button(callback, state)
    elif callback.data == "skip_buttons":
        await skip_buttons(callback, state)
    elif callback.data == "finish_ad":
        await finish_ad(callback, state)
    elif callback.data.startswith("audience_"):
        await handle_audience_selection(callback, state)
    elif callback.data == "select_audience_from_buttons":
        await select_audience(callback, state)
    elif callback.data == "save_ad":
        await save_ad(callback, state)
    elif callback.data.startswith("confirm_send_"):
        await confirm_ad(callback, state)
    elif callback.data.startswith("reject_send_"):
        await reject_ad(callback, state)
    elif callback.data == "cancel_ad":
        await cancel_ad(callback, state)
    elif callback.data == "back_to_main":
        await show_main_menu(callback)
    
    await callback.answer()

async def show_main_menu(callback: types.CallbackQuery):
    """Show main admin menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ заборонено", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скарги", callback_data="admin_complaints")],
            [InlineKeyboardButton(text="📢 Розсилка та реклама", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📺 Канали", callback_data="admin_channels")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
        ]
    )
    
    try:
        await callback.message.edit_text(
            f"🔧 **Адміністративна панель**\n\n"
            f"Керування ботом {MAIN_BOT_USERNAME}\n\n"
            f"Виберіть дію:",
            reply_markup=keyboard
        )
    except Exception:
        await callback.message.answer(
            f"🔧 **Адміністративна панель**\n\n"
            f"Керування ботом {MAIN_BOT_USERNAME}\n\n"
            f"Виберіть дію:",
            reply_markup=keyboard
        )

async def show_complaints(callback: types.CallbackQuery):
    """Show complaints overview with statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get users who have 20+ rejected complaints
    cur.execute('''
    SELECT reported_user_id, COUNT(*) as rejected_count
    FROM complaints 
    WHERE status = 'rejected'
    GROUP BY reported_user_id
    HAVING COUNT(*) >= 20
    ''')
    users_with_20_plus = [row[0] for row in cur.fetchall()]
    
    # Get complaints statistics - count users with 20+ rejected complaints
    total_complaints = len(users_with_20_plus)
    
    # Count users with 20+ rejected complaints who also have pending complaints
    if users_with_20_plus:
        placeholders = ','.join(['?' for _ in users_with_20_plus])
        cur.execute(f'''
        SELECT COUNT(DISTINCT reported_user_id) 
        FROM complaints 
        WHERE status = 'pending' AND reported_user_id IN ({placeholders})
        ''', users_with_20_plus)
        active_complaints = cur.fetchone()[0]
        
        cur.execute(f'''
        SELECT COUNT(DISTINCT reported_user_id) 
        FROM complaints 
        WHERE status = 'rejected' AND reported_user_id IN ({placeholders})
        ''', users_with_20_plus)
        rejected_complaints = cur.fetchone()[0]
        
        # Get unique reported users with pending complaints who have 20+ rejected complaints
        cur.execute(f'''
        SELECT reported_user_id, COUNT(*) as complaint_count, MIN(id) as first_complaint_id
        FROM complaints 
        WHERE status = 'pending' AND reported_user_id IN ({placeholders})
        GROUP BY reported_user_id
        ORDER BY complaint_count DESC, first_complaint_id ASC
        ''', users_with_20_plus)
    else:
        active_complaints = 0
        rejected_complaints = 0
        cur.execute('SELECT NULL LIMIT 0')  # Empty result
    
    reported_users = cur.fetchall()
    conn.close()
    
    # Create text with statistics
    text = "📋 **Система скарг**\n\n"
    text += f"📊 **Статистика:**\n"
    text += f"• Всього скарг: {total_complaints}\n"
    text += f"• Активних скарг: {active_complaints}\n"
    text += f"• Відхилених скарг: {rejected_complaints}\n\n"
    
    keyboard_buttons = []
    
    if reported_users:
        text += "👥 **Користувачі зі скаргами доступні через кнопки нижче**"
        
        for reported_user_id, complaint_count, _ in reported_users:
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"#{reported_user_id} ({complaint_count} скарг)",
                callback_data=f"complaint_user_{reported_user_id}"
            )])
    else:
        text += "✅ Немає активних скарг"
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

async def show_complaint_user_details(callback: types.CallbackQuery, user_id: int):
    """Show detailed information about user with complaints"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get user info
    user_data = get_user_info_for_admin(user_id)
    if not user_data:
        await callback.answer("❌ Користувача не знайдено", show_alert=True)
        return
    
    # Get complaints for this user
    cur.execute('''
    SELECT COUNT(*) FROM complaints 
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (user_id,))
    pending_complaints = cur.fetchone()[0]
    
    conn.close()
    
    # Format user information
    text = f"👤 **Інформація про користувача**\n\n"
    text += f"🆔 **ID:** {user_data['user_id']}\n"
    
    if user_data.get('username'):
        text += f"📝 **Username:** @{user_data['username']}\n"
    
    if user_data.get('first_name'):
        text += f"👤 **Ім'я:** {user_data['first_name']}\n"
    
    if user_data.get('age'):
        text += f"🎂 **Вік:** {user_data['age']}\n"
    
    if user_data.get('gender'):
        text += f"⚧ **Стать:** {user_data['gender']}\n"
    
    if user_data.get('country'):
        text += f"🌍 **Країна:** {user_data['country']}\n"
    
    text += f"📊 **Статус:** {user_data['status']}\n"
    
    if user_data.get('registration_date'):
        text += f"📅 **Реєстрація:** {user_data['registration_date']}\n"
    
    text += f"💬 **Бесід проведено:** {user_data['chats_count']}\n"
    
    # Show ratings - always show all types
    ratings = user_data.get('ratings', {})
    text += f"\n⭐ **Реакції:**\n"
    text += f"👍 Добре: {ratings.get('good', 0)}\n"
    text += f"👎 Погано: {ratings.get('bad', 0)}\n"
    text += f"❤️ Супер: {ratings.get('super', 0)}\n"
    
    text += f"\n📋 **Кількість скарг:** {pending_complaints}\n"
    
    # Create keyboard with action buttons
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Заблокувати", callback_data=f"complaint_block_{user_id}"),
                InlineKeyboardButton(text="✅ Відхилити", callback_data=f"complaint_dismiss_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Показати розмови", callback_data=f"complaint_conversations_{user_id}")],
            [InlineKeyboardButton(text="🔙 До скарг", callback_data="admin_complaints")]
        ]
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

async def show_complaint_user_details_new(callback: types.CallbackQuery, user_id: int):
    """Show detailed information about user with complaints (send new message)"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get user info
    user_data = get_user_info_for_admin(user_id)
    if not user_data:
        await callback.answer("❌ Користувача не знайдено", show_alert=True)
        return
    
    # Get pending complaints count
    cur.execute('SELECT COUNT(*) FROM complaints WHERE reported_user_id = ? AND status = "pending"', (user_id,))
    pending_complaints = cur.fetchone()[0]
    
    conn.close()
    
    # Create detailed user info text
    text = f"👤 **Інформація про користувача #{user_id}**\n\n"
    
    # Basic info
    text += f"🆔 **ID:** {user_id}\n"
    if user_data.get('username'):
        text += f"👤 **Username:** @{user_data['username']}\n"
    if user_data.get('first_name'):
        text += f"📝 **Ім'я:** {user_data['first_name']}\n"
    
    # Profile info
    if user_data.get('age'):
        text += f"🎂 **Вік:** {user_data['age']}\n"
    if user_data.get('gender'):
        gender_emoji = "👨" if user_data['gender'] == 'male' else "👩"
        text += f"{gender_emoji} **Стать:** {user_data['gender']}\n"
    if user_data.get('country'):
        text += f"🌍 **Країна:** {user_data['country']}\n"
    
    # Status and registration
    from premium_aiogram import get_user_status
    status = get_user_status(user_id)
    status_emoji = " 🌟" if status == 'pro' else " 💎" if status == 'premium' else ""
    text += f"⭐ **Статус:** {status.title()}{status_emoji}\n"
    
    if user_data.get('registration_date'):
        text += f"📅 **Дата реєстрації:** {user_data['registration_date']}\n"
    
    # Statistics
    if user_data.get('chats_count'):
        text += f"💬 **Кількість бесід:** {user_data['chats_count']}\n"
    
    # Ratings - always show all types
    from user_profile_aiogram import get_user_ratings
    ratings = get_user_ratings(user_id)
    text += f"\n⭐ **Реакції:**\n"
    text += f"👍 Добре: {ratings.get('good', 0) if ratings else 0}\n"
    text += f"👎 Погано: {ratings.get('bad', 0) if ratings else 0}\n"
    text += f"❤️ Супер: {ratings.get('super', 0) if ratings else 0}\n"
    
    text += f"\n📋 **Кількість скарг:** {pending_complaints}\n"
    
    # Create keyboard with action buttons
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Заблокувати", callback_data=f"complaint_block_{user_id}"),
                InlineKeyboardButton(text="✅ Відхилити", callback_data=f"complaint_dismiss_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Показати розмови", callback_data=f"complaint_conversations_{user_id}")],
            [InlineKeyboardButton(text="🔙 До скарг", callback_data="admin_complaints")]
        ]
    )
    
    await callback.message.answer(text, reply_markup=keyboard)

async def block_user_from_complaints(callback: types.CallbackQuery, user_id: int):
    """Block user and mark all their complaints as accepted"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Add user to blocked list
    cur.execute('''
    INSERT OR REPLACE INTO blocked_users (user_id, blocked_by, reason, timestamp)
    VALUES (?, ?, ?, ?)
    ''', (user_id, callback.from_user.id, "Заблоковано через скарги", int(time.time())))
    
    # Mark all pending complaints for this user as accepted
    cur.execute('''
    UPDATE complaints 
    SET status = 'accepted', admin_response = 'Користувача заблоковано', response_date = ?
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (int(time.time()), user_id))
    
    # Delete stored conversations for this user
    cur.execute('DELETE FROM user_conversations WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    await callback.answer("✅ Користувача заблоковано", show_alert=True)
    await show_complaints(callback)

async def dismiss_user_complaints(callback: types.CallbackQuery, user_id: int):
    """Dismiss all complaints for user and increment rejected count"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current rejected count for this user
    cur.execute('''
    SELECT COALESCE(MAX(rejected_count), 0) FROM complaints 
    WHERE reported_user_id = ?
    ''', (user_id,))
    current_rejected_count = cur.fetchone()[0]
    new_rejected_count = current_rejected_count + 1
    
    # Mark all pending complaints for this user as rejected
    cur.execute('''
    UPDATE complaints 
    SET status = 'rejected', admin_response = 'Скарги відхилено', response_date = ?, rejected_count = ?
    WHERE reported_user_id = ? AND status = 'pending'
    ''', (int(time.time()), new_rejected_count, user_id))
    
    # Check if user has reached 20 rejected complaints threshold
    if new_rejected_count >= 20:
        # Reset rejected count and make complaints pending again for review
        cur.execute('''
        INSERT INTO complaints (reporter_id, reported_user_id, reason, timestamp, status)
        VALUES (?, ?, ?, ?, 'pending')
        ''', (0, user_id, f"Автоматична скарга: користувач накопичив {new_rejected_count} відхилених скарг", int(time.time())))
        
        # Reset rejected count
        cur.execute('''
        UPDATE complaints 
        SET rejected_count = 0 
        WHERE reported_user_id = ?
        ''', (user_id,))
    else:
        # Delete stored conversations for this user since complaints are dismissed
        cur.execute('DELETE FROM user_conversations WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    if new_rejected_count >= 20:
        await callback.answer(f"⚠️ Скарги відхилено. Користувач накопичив {new_rejected_count} відхилених скарг і повернувся до розгляду", show_alert=True)
    else:
        await callback.answer("✅ Скарги відхилено", show_alert=True)
    
    await show_complaints(callback)

async def show_user_conversations(callback: types.CallbackQuery, user_id: int):
    """Show last 3 conversations for user"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get last 3 conversations
    cur.execute('''
    SELECT partner_id, conversation_data, timestamp 
    FROM user_conversations 
    WHERE user_id = ? 
    ORDER BY timestamp DESC 
    LIMIT 3
    ''', (user_id,))
    
    conversations = cur.fetchall()
    conn.close()
    
    if not conversations:
        await callback.answer("❌ Немає збережених розмов", show_alert=True)
        return
    
    # Store message IDs for later deletion
    conversation_message_ids = []
    
    # Send each conversation as separate message
    for i, (partner_id, conversation_data, timestamp) in enumerate(conversations, 1):
        date_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(timestamp))
        
        # Replace old names with new ones in conversation data
        conversation_data = conversation_data.replace("Ви:", "Підозрюваний:")
        conversation_data = conversation_data.replace(f"Співрозмовник ({partner_id}):", "Інкогніто:")
        
        text = f"💬 **Розмова #{i}**\n"
        text += f"👥 **Інкогніто:** {partner_id}\n"
        text += f"📅 **Дата:** {date_str}\n\n"
        text += f"**Зміст розмови:**\n{conversation_data}"
        
        msg = await callback.message.answer(text)
        conversation_message_ids.append(msg.message_id)
    
    # Show return button with stored message IDs
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад до користувача", callback_data=f"complaint_user_{user_id}_delete_{','.join(map(str, conversation_message_ids))}")]
        ]
    )
    
    final_msg = await callback.message.answer("📋 Всі збережені розмови показано вище", reply_markup=keyboard)
    conversation_message_ids.append(final_msg.message_id)
    
    # Update the callback data to include all message IDs
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад до користувача", callback_data=f"complaint_user_{user_id}_delete_{','.join(map(str, conversation_message_ids))}")]
        ]
    )
    
    await final_msg.edit_reply_markup(reply_markup=keyboard)

async def show_broadcast_menu(callback: types.CallbackQuery):
    """Show broadcast menu"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Створити рекламу", callback_data="create_ad")],
            [InlineKeyboardButton(text="📋 Дійсні реклами", callback_data="active_ads")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )
    
    try:
        await callback.message.edit_text(
            "🎯 **Реклама**\n\n"
            "Виберіть дію:",
            reply_markup=keyboard
        )
    except Exception:
        await callback.message.answer(
            "🎯 **Реклама**\n\n"
            "Виберіть дію:",
            reply_markup=keyboard
        )

async def show_channels_menu(callback: types.CallbackQuery):
    """Show channels management menu"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM required_channels WHERE is_active = 1')
    active_channels = cur.fetchone()[0]
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати канал", callback_data="channel_add")],
            [InlineKeyboardButton(text="📋 Список каналів", callback_data="channel_list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )
    
    try:
        await callback.message.edit_text(
            f"📺 **Управління каналами**\n\n"
            f"Активних каналів: {active_channels}\n\n"
            f"Виберіть дію:",
            reply_markup=keyboard
        )
    except Exception:
        await callback.message.answer(
            f"📺 **Управління каналами**\n\n"
            f"Активних каналів: {active_channels}\n\n"
            f"Виберіть дію:",
            reply_markup=keyboard
        )


async def handle_complaint_action(callback: types.CallbackQuery):
    """Handle complaint-related actions"""
    action = callback.data.split("_")[1]
    complaint_id = int(callback.data.split("_")[2])
    
    if action == "view":
        await show_complaint_details(callback, complaint_id)
    elif action == "accept":
        await accept_complaint(callback, complaint_id)
    elif action == "reject":
        await reject_complaint(callback, complaint_id)

async def show_complaint_details(callback: types.CallbackQuery, complaint_id: int):
    """Show detailed complaint information"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT reporter_id, reported_user_id, reason, timestamp
    FROM complaints WHERE id = ?
    ''', (complaint_id,))
    
    complaint = cur.fetchone()
    conn.close()
    
    if not complaint:
        await callback.message.edit_text("❌ Скарга не знайдена")
        return
    
    reporter_id, reported_id, reason, timestamp = complaint
    date_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(timestamp))
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Прийняти", callback_data=f"complaint_accept_{complaint_id}"),
                InlineKeyboardButton(text="❌ Відхилити", callback_data=f"complaint_reject_{complaint_id}")
            ],
            [InlineKeyboardButton(text="🔙 До скарг", callback_data="admin_complaints")]
        ]
    )
    
    detail_text = (
        f"📋 **Скарга #{complaint_id}**\n\n"
        f"👤 **Скаржник:** {reporter_id}\n"
        f"🎯 **На користувача:** {reported_id}\n"
        f"📅 **Дата:** {date_str}\n\n"
        f"📝 **Причина скарги:**\n{reason if reason else 'Порушення правил'}"
    )
    
    await callback.message.edit_text(detail_text, reply_markup=keyboard)

async def accept_complaint(callback: types.CallbackQuery, complaint_id: int):
    """Accept and process complaint"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get complaint details
    cur.execute('''
    SELECT reporter_id, reported_user_id, reason
    FROM complaints WHERE id = ?
    ''', (complaint_id,))
    
    complaint = cur.fetchone()
    if not complaint:
        await callback.message.edit_text("❌ Скарга не знайдена")
        return
    
    reporter_id, reported_user_id, reason = complaint
    
    # Update complaint status
    cur.execute('''
    UPDATE complaints 
    SET status = 'accepted', admin_response = 'Прийнято адміністратором', response_date = ?
    WHERE id = ?
    ''', (int(time.time()), complaint_id))
    
    conn.commit()
    conn.close()
    
    # You can add additional actions here like blocking the user
    # For now, just mark as accepted
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 До скарг", callback_data="admin_complaints")]
        ]
    )
    
    await callback.message.edit_text(
        f"✅ **Скарга #{complaint_id} прийнята**\n\n"
        f"👤 Скаржник: {reporter_id}\n"
        f"🎯 На користувача: {reported_user_id}\n"
        f"📝 Причина: {reason if reason else 'Порушення правил'}\n\n"
        f"⚠️ Скарга відмічена як обґрунтована.",
        reply_markup=keyboard
    )

async def reject_complaint(callback: types.CallbackQuery, complaint_id: int):
    """Reject complaint"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get complaint details
    cur.execute('''
    SELECT reporter_id, reported_user_id, reason
    FROM complaints WHERE id = ?
    ''', (complaint_id,))
    
    complaint = cur.fetchone()
    if not complaint:
        await callback.message.edit_text("❌ Скарга не знайдена")
        return
    
    reporter_id, reported_user_id, reason = complaint
    
    # Update complaint status
    cur.execute('''
    UPDATE complaints 
    SET status = 'rejected', admin_response = 'Відхилено адміністратором', response_date = ?
    WHERE id = ?
    ''', (int(time.time()), complaint_id))
    
    conn.commit()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 До скарг", callback_data="admin_complaints")]
        ]
    )
    
    await callback.message.edit_text(
        f"❌ **Скарга #{complaint_id} відхилена**\n\n"
        f"👤 Скаржник: {reporter_id}\n"
        f"🎯 На користувача: {reported_user_id}\n"
        f"📝 Причина: {reason if reason else 'Порушення правил'}\n\n"
        f"ℹ️ Скарга відмічена як необґрунтована.",
        reply_markup=keyboard
    )

async def handle_channel_action(callback: types.CallbackQuery, state: FSMContext):
    """Handle channel-related actions"""
    if callback.data == "channel_add":
        try:
            await callback.message.edit_text(
                "➕ **Додавання каналу**\n\n"
                "Надішліть посилання на канал (наприклад: https://t.me/channel_name):"
            )
        except Exception:
            await callback.message.answer(
                "➕ **Додавання каналу**\n\n"
                "Надішліть посилання на канал (наприклад: https://t.me/channel_name):"
            )
        await state.set_state(AdminStates.waiting_for_channel_url)
    elif callback.data == "channel_list":
        await show_channels_list(callback)
    elif callback.data.startswith("channel_delete_"):
        await delete_channel(callback)
    elif callback.data.startswith("channel_toggle_"):
        # Existing toggle functionality
        pass

async def show_channels_list(callback: types.CallbackQuery):
    """Show list of required channels"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    SELECT id, channel_name, channel_url, is_active
    FROM required_channels
    ORDER BY added_date DESC
    ''')
    
    channels = cur.fetchall()
    conn.close()
    
    if not channels:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Додати канал", callback_data="channel_add")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_channels")]
            ]
        )
        try:
            await callback.message.edit_text(
                "📺 **Список каналів**\n\n"
                "Немає доданих каналів",
                reply_markup=keyboard
            )
        except Exception:
            await callback.message.answer(
                "📺 **Список каналів**\n\n"
                "Немає доданих каналів",
                reply_markup=keyboard
            )
        return
    
    text = "📺 **Обов'язкові канали:**\n\n"
    keyboard_buttons = []
    
    for channel in channels:
        channel_id, name, url, is_active = channel
        status = "✅" if is_active else "❌"
        text += f"{status} **{name}**\n{url}\n\n"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{'🔴 Деактивувати' if is_active else '🟢 Активувати'} {name}",
                callback_data=f"channel_toggle_{channel_id}"
            ),
            InlineKeyboardButton(
                text=f"🗑️ Видалити {name}",
                callback_data=f"channel_delete_{channel_id}"
            )
        ])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="➕ Додати канал", callback_data="channel_add")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_channels")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

@dp.message(AdminStates.waiting_for_channel_url)
async def process_channel_url(message: Message, state: FSMContext):
    """Process channel URL input"""
    if not is_admin(message.from_user.id):
        return
    
    url = message.text.strip()
    
    # Basic URL validation
    if not (url.startswith("https://t.me/") or url.startswith("@")):
        await message.answer("❌ Неправильний формат посилання. Використовуйте: https://t.me/channel_name або @channel_name")
        return
    
    await state.update_data(channel_url=url)
    await message.answer("📝 Тепер надішліть назву каналу (як буде відображатися користувачам):")
    await state.set_state(AdminStates.waiting_for_channel_name)

@dp.message(AdminStates.waiting_for_channel_name)
async def process_channel_name(message: Message, state: FSMContext):
    """Process channel name input"""
    if not is_admin(message.from_user.id):
        return
    
    name = message.text.strip()
    data = await state.get_data()
    url = data.get('channel_url')
    
    # Save to database
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT INTO required_channels (channel_url, channel_name, added_date)
    VALUES (?, ?, ?)
    ''', (url, name, int(time.time())))
    
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ **Канал додано!**\n\n"
        f"📺 **Назва:** {name}\n"
        f"🔗 **Посилання:** {url}\n\n"
        f"Користувачі тепер повинні підписатися на цей канал для використання бота."
    )
    
    await state.clear()

def add_complaint(reporter_id, reported_user_id, reason="Порушення правил"):
    """Add new complaint to database"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT INTO complaints (reporter_id, reported_user_id, reason, timestamp)
    VALUES (?, ?, ?, ?)
    ''', (reporter_id, reported_user_id, reason, int(time.time())))
    
    conn.commit()
    conn.close()

def init_ads_table():
    """Initialize advertisements table"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS advertisements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        message TEXT NOT NULL,
        media_type TEXT,
        media_file_id TEXT,
        buttons TEXT,
        audience TEXT DEFAULT 'all',
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # Add audience column if it doesn't exist (for existing tables)
    try:
        cur.execute('ALTER TABLE advertisements ADD COLUMN audience TEXT DEFAULT "all"')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()


async def create_ad(callback: types.CallbackQuery, state: FSMContext):
    """Start creating advertisement"""
    await state.set_state(AdminStates.waiting_for_ad_name)
    try:
        await callback.message.edit_text(
            "🎯 **Створення реклами**\n\n"
            "📝 Введіть назву реклами (використовуватиметься для назви кнопок):"
        )
    except Exception:
        await callback.message.answer(
            "🎯 **Створення реклами**\n\n"
            "📝 Введіть назву реклами (використовуватиметься для назви кнопок):"
        )

async def show_active_ads(callback: types.CallbackQuery):
    """Show active advertisements"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT id, name, created_at FROM advertisements WHERE is_active = 1 ORDER BY created_at DESC')
    ads = cur.fetchall()
    conn.close()
    
    if not ads:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Створити рекламу", callback_data="create_ad")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_ads")]
            ]
        )
        try:
            await callback.message.edit_text(
                "📋 **Дійсні реклами**\n\n"
                "✅ Немає активних реклам",
                reply_markup=keyboard
            )
        except Exception:
            await callback.message.answer(
                "📋 **Дійсні реклами**\n\n"
                "✅ Немає активних реклам",
                reply_markup=keyboard
            )
        return
    
    text = "📋 **Дійсні реклами**\n\n"
    keyboard_buttons = []
    
    for ad in ads:
        ad_id, name, created_at = ad
        created_date = time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))
        text += f"🎯 **{name}**\n📅 {created_date}\n\n"
        
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"👁️ {name}", callback_data=f"view_ad_{ad_id}"),
            InlineKeyboardButton(text=f"🗑️ Видалити", callback_data=f"delete_ad_{ad_id}")
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_ads")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

async def delete_channel(callback: types.CallbackQuery):
    """Delete channel"""
    channel_id = int(callback.data.split('_')[2])
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get channel name for confirmation
    cur.execute('SELECT channel_name FROM required_channels WHERE id = ?', (channel_id,))
    result = cur.fetchone()
    
    if result:
        channel_name = result[0]
        # Delete channel
        cur.execute('DELETE FROM required_channels WHERE id = ?', (channel_id,))
        conn.commit()
        
        await callback.answer(f"✅ Канал '{channel_name}' видалено!")
        # Refresh channel list
        await show_channels_list(callback)
    else:
        await callback.answer("❌ Канал не знайдено!")
    
    conn.close()

# Advertisement creation handlers
@dp.message(AdminStates.waiting_for_ad_name)
async def process_ad_name(message: Message, state: FSMContext):
    """Process advertisement name"""
    if not is_admin(message.from_user.id):
        return
    
    ad_name = message.text.strip()
    await state.update_data(ad_name=ad_name)
    await state.set_state(AdminStates.waiting_for_ad_media)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустити медіа", callback_data="skip_media")]
        ]
    )
    
    await message.answer(
        f"🎯 **Створення реклами: {ad_name}**\n\n"
        f"📸 Завантажте медіа (фото, відео, документ) або натисніть 'Пропустити':",
        reply_markup=keyboard
    )

@dp.message(AdminStates.waiting_for_ad_media)
async def process_ad_media(message: Message, state: FSMContext):
    """Process advertisement media"""
    if not is_admin(message.from_user.id):
        return
    
    media_type = None
    media_file_id = None
    
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    
    await state.update_data(media_type=media_type, media_file_id=media_file_id)
    await state.set_state(AdminStates.waiting_for_ad_message)
    
    await message.answer(
        "📝 **Текст повідомлення**\n\n"
        "Введіть текст реклами:"
    )

@dp.message(AdminStates.waiting_for_ad_message)
async def process_ad_message(message: Message, state: FSMContext):
    """Process advertisement message"""
    if not is_admin(message.from_user.id):
        return
    
    ad_message = message.text.strip()
    await state.update_data(ad_message=ad_message)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати кнопку", callback_data="add_button")],
            [InlineKeyboardButton(text="⏭️ Пропустити кнопки", callback_data="skip_buttons")]
        ]
    )
    
    await message.answer(
        "🔘 **Кнопки реклами**\n\n"
        "Додайте кнопки з назвами та посиланнями або пропустіть:",
        reply_markup=keyboard
    )

@dp.message(AdminStates.waiting_for_button_name)
async def process_button_name(message: Message, state: FSMContext):
    """Process button name"""
    if not is_admin(message.from_user.id):
        return
    
    button_name = message.text.strip()
    await state.update_data(current_button_name=button_name)
    await state.set_state(AdminStates.waiting_for_button_url)
    
    await message.answer(
        f"🔗 **Посилання для кнопки '{button_name}'**\n\n"
        f"Введіть URL посилання:"
    )

@dp.message(AdminStates.waiting_for_button_url)
async def process_button_url(message: Message, state: FSMContext):
    """Process button URL"""
    if not is_admin(message.from_user.id):
        return
    
    button_url = message.text.strip()
    data = await state.get_data()
    
    # Add button to buttons list
    buttons = data.get('buttons', [])
    buttons.append({
        'name': data['current_button_name'],
        'url': button_url
    })
    await state.update_data(buttons=buttons)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати ще кнопку", callback_data="add_button")],
            [InlineKeyboardButton(text="✅ Завершити", callback_data="select_audience_from_buttons")]
        ]
    )
    
    await message.answer(
        f"✅ Кнопка '{data['current_button_name']}' додана!\n\n"
        f"Всього кнопок: {len(buttons)}\n\n"
        f"Додати ще кнопку або завершити створення?",
        reply_markup=keyboard
    )

async def skip_media(callback: types.CallbackQuery, state: FSMContext):
    """Skip media step"""
    await state.update_data(media_type=None, media_file_id=None)
    await state.set_state(AdminStates.waiting_for_ad_message)
    
    try:
        await callback.message.edit_text(
            "📝 **Текст повідомлення**\n\n"
            "Введіть текст реклами:"
        )
    except Exception:
        await callback.message.answer(
            "📝 **Текст повідомлення**\n\n"
            "Введіть текст реклами:"
        )

async def add_button(callback: types.CallbackQuery, state: FSMContext):
    """Add button to advertisement"""
    await state.set_state(AdminStates.waiting_for_button_name)
    
    try:
        await callback.message.edit_text(
            "🔘 **Назва кнопки**\n\n"
            "Введіть назву кнопки:"
        )
    except Exception:
        await callback.message.answer(
            "🔘 **Назва кнопки**\n\n"
            "Введіть назву кнопки:"
        )

async def skip_buttons(callback: types.CallbackQuery, state: FSMContext):
    """Skip buttons and go to audience selection"""
    await state.update_data(buttons=[])
    await select_audience(callback, state)

async def select_audience(callback: types.CallbackQuery, state: FSMContext):
    """Select target audience for advertisement"""
    await state.set_state(AdminStates.waiting_for_ad_audience)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Звичайні користувачі", callback_data="audience_regular")],
            [InlineKeyboardButton(text="💎 Premium користувачі", callback_data="audience_premium")],
            [InlineKeyboardButton(text="🌟 PRO користувачі", callback_data="audience_pro")],
            [InlineKeyboardButton(text="👥 Всі користувачі", callback_data="audience_all")]
        ]
    )
    
    await callback.message.edit_text(
        "🎯 **Вибір аудиторії**\n\n"
        "Оберіть кому буде надіслана реклама:",
        reply_markup=keyboard
    )

async def handle_audience_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle audience selection"""
    audience_type = callback.data.replace("audience_", "")
    
    audience_names = {
        "regular": "👤 Звичайні користувачі",
        "premium": "💎 Premium користувачі", 
        "pro": "🌟 PRO користувачі",
        "all": "👥 Всі користувачі"
    }
    
    await state.update_data(audience=audience_type)
    
    await callback.message.edit_text(
        f"✅ **Аудиторію обрано:** {audience_names[audience_type]}\n\n"
        "Переходимо до попереднього перегляду...",
    )
    
    # Small delay then show preview
    import asyncio
    await asyncio.sleep(1)
    await finish_ad(callback, state)

async def finish_ad(callback: types.CallbackQuery, state: FSMContext):
    """Finish creating advertisement and show preview"""
    data = await state.get_data()
    
    # Show preview as it will appear in main bot
    await show_ad_preview(callback, data, state)

async def show_ad_preview(callback: types.CallbackQuery, data: dict, state: FSMContext):
    """Show advertisement preview as it will appear in main bot"""
    # Create buttons for the ad
    ad_buttons = []
    if data.get('buttons'):
        for button in data['buttons']:
            ad_buttons.append([InlineKeyboardButton(text=button['name'], url=button['url'])])
    
    # Add confirmation buttons
    confirm_buttons = [
        [InlineKeyboardButton(text="✅ Зберегти рекламу", callback_data="save_ad")],
        [InlineKeyboardButton(text="❌ Відхилити", callback_data="cancel_ad")]
    ]
    
    # Combine ad buttons with confirmation buttons
    all_buttons = ad_buttons + confirm_buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=all_buttons)
    
    # Show preview message
    audience_names = {
        "regular": "👤 Звичайні користувачі",
        "premium": "💎 Premium користувачі", 
        "pro": "🌟 PRO користувачі",
        "all": "👥 Всі користувачі"
    }
    audience_text = audience_names.get(data.get('audience', 'all'), "👥 Всі користувачі")
    
    preview_header = f"🎯 **Попередній перегляд реклами '{data['ad_name']}'**\n\n"
    preview_header += f"📊 **Аудиторія:** {audience_text}\n"
    preview_header += "─" * 30 + "\n"
    preview_header += "**Так виглядатиме реклама в основному боті:**\n\n"
    
    ad_text = data['ad_message']
    full_text = preview_header + ad_text
    
    # Send with media if available
    if data.get('media_type') and data.get('media_file_id'):
        if data['media_type'] == 'photo':
            await callback.message.delete()
            await admin_bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=data['media_file_id'],
                caption=full_text,
                reply_markup=keyboard
            )
        elif data['media_type'] == 'video':
            await callback.message.delete()
            await admin_bot.send_video(
                chat_id=callback.message.chat.id,
                video=data['media_file_id'],
                caption=full_text,
                reply_markup=keyboard
            )
        elif data['media_type'] == 'document':
            await callback.message.delete()
            await admin_bot.send_document(
                chat_id=callback.message.chat.id,
                document=data['media_file_id'],
                caption=full_text,
                reply_markup=keyboard
            )
    else:
        await callback.message.edit_text(full_text, reply_markup=keyboard)

async def delete_ad(callback: types.CallbackQuery):
    """Delete advertisement"""
    ad_id = int(callback.data.split('_')[2])
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get ad name for confirmation
    cur.execute('SELECT name FROM advertisements WHERE id = ?', (ad_id,))
    result = cur.fetchone()
    
    if result:
        ad_name = result[0]
        # Delete advertisement
        cur.execute('DELETE FROM advertisements WHERE id = ?', (ad_id,))
        conn.commit()
        
        await callback.answer(f"✅ Рекламу '{ad_name}' видалено!")
        # Refresh ads list
        await show_active_ads(callback)
    else:
        await callback.answer("❌ Рекламу не знайдено!")
    
    conn.close()

async def view_ad(callback: types.CallbackQuery):
    """View advertisement details"""
    ad_id = int(callback.data.split('_')[2])
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM advertisements WHERE id = ?', (ad_id,))
    ad = cur.fetchone()
    conn.close()
    
    if not ad:
        await callback.answer("❌ Рекламу не знайдено!")
        return
    
    ad_id, name, message, media_type, media_file_id, buttons_json, created_at, is_active = ad
    
    import json
    buttons = json.loads(buttons_json) if buttons_json else []
    
    text = f"🎯 **{name}**\n\n"
    text += f"📅 Створено: {time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))}\n"
    text += f"📸 Медіа: {'Так' if media_type else 'Ні'}\n"
    text += f"🔘 Кнопок: {len(buttons)}\n"
    text += f"📊 Статус: {'Активна' if is_active else 'Неактивна'}\n\n"
    text += f"**Текст:**\n{message}\n\n"
    
    if buttons:
        text += "**Кнопки:**\n"
        for i, button in enumerate(buttons, 1):
            text += f"{i}. {button['name']} → {button['url']}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_ad_{ad_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="active_ads")]
        ]
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

async def save_ad(callback: types.CallbackQuery, state: FSMContext):
    """Save advertisement and send for admin confirmation"""
    data = await state.get_data()
    
    # Save to database
    conn = get_conn()
    cur = conn.cursor()
    
    import json
    buttons_json = json.dumps(data.get('buttons', []))
    
    cur.execute('''
    INSERT INTO advertisements (name, message, media_type, media_file_id, buttons, audience, is_active)
    VALUES (?, ?, ?, ?, ?, ?, 0)
    ''', (
        data['ad_name'],
        data['ad_message'],
        data.get('media_type'),
        data.get('media_file_id'),
        buttons_json,
        data.get('audience', 'all')
    ))
    
    ad_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    await state.clear()
    
    # Send confirmation message to admin
    await send_ad_for_confirmation(ad_id, data)
    
    # Try to edit text, if fails - send new message
    try:
        await callback.message.edit_text(
            f"✅ **Рекламу збережено!**\n\n"
            f"📝 Назва: {data['ad_name']}\n"
            f"🆔 ID реклами: {ad_id}\n\n"
            f"📋 Реклама надіслана для підтвердження.\n"
            f"Після підтвердження вона буде розіслана користувачам.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 До головного меню", callback_data="back_to_main")]
                ]
            )
        )
    except Exception as e:
        # If edit fails, send new message
        await callback.message.answer(
            f"✅ **Рекламу збережено!**\n\n"
            f"📝 Назва: {data['ad_name']}\n"
            f"🆔 ID реклами: {ad_id}\n\n"
            f"📋 Реклама надіслана для підтвердження.\n"
            f"Після підтвердження вона буде розіслана користувачам.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 До головного меню", callback_data="back_to_main")]
                ]
            )
        )

async def send_ad_for_confirmation(ad_id: int, data: dict):
    """Send advertisement to admin for confirmation"""
    audience_names = {
        "regular": "👤 Звичайні користувачі",
        "premium": "💎 Premium користувачі", 
        "pro": "🌟 PRO користувачі",
        "all": "👥 Всі користувачі"
    }
    audience_text = audience_names.get(data.get('audience', 'all'), "👥 Всі користувачі")
    
    # Create ad buttons
    ad_buttons = []
    if data.get('buttons'):
        for button in data['buttons']:
            ad_buttons.append([InlineKeyboardButton(text=button['name'], url=button['url'])])
    
    # Add confirmation buttons
    confirm_buttons = [
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_send_{ad_id}")],
        [InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_send_{ad_id}")]
    ]
    
    all_buttons = ad_buttons + confirm_buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=all_buttons)
    
    confirmation_text = f"🎯 **Підтвердження розсилки реклами**\n\n"
    confirmation_text += f"📝 **Назва:** {data['ad_name']}\n"
    confirmation_text += f"📊 **Аудиторія:** {audience_text}\n"
    confirmation_text += f"🆔 **ID:** {ad_id}\n\n"
    confirmation_text += "─" * 30 + "\n"
    confirmation_text += "**Реклама:**\n\n"
    confirmation_text += data['ad_message']
    
    # Send with media if available
    if data.get('media_type') and data.get('media_file_id'):
        if data['media_type'] == 'photo':
            await admin_bot.send_photo(
                chat_id=ADMIN_USER_ID,
                photo=data['media_file_id'],
                caption=confirmation_text,
                reply_markup=keyboard
            )
        elif data['media_type'] == 'video':
            await admin_bot.send_video(
                chat_id=ADMIN_USER_ID,
                video=data['media_file_id'],
                caption=confirmation_text,
                reply_markup=keyboard
            )
        elif data['media_type'] == 'document':
            await admin_bot.send_document(
                chat_id=ADMIN_USER_ID,
                document=data['media_file_id'],
                caption=confirmation_text,
                reply_markup=keyboard
            )
    else:
        await admin_bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=confirmation_text,
            reply_markup=keyboard
        )

async def confirm_ad(callback: types.CallbackQuery, state: FSMContext):
    """Confirm and send advertisement to main bot"""
    ad_id = int(callback.data.replace("confirm_send_", ""))
    
    # Get ad from database
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM advertisements WHERE id = ?', (ad_id,))
    ad_row = cur.fetchone()
    
    if not ad_row:
        await callback.answer("❌ Реклама не знайдена", show_alert=True)
        return
    
    # Update ad as active
    cur.execute('UPDATE advertisements SET is_active = 1 WHERE id = ?', (ad_id,))
    conn.commit()
    conn.close()
    
    # Prepare ad data
    import json
    ad_data = {
        'ad_name': ad_row[1],
        'ad_message': ad_row[2],
        'media_type': ad_row[3],
        'media_file_id': ad_row[4],
        'buttons': json.loads(ad_row[5]) if ad_row[5] else [],
        'audience': ad_row[6] if len(ad_row) > 6 else 'all'
    }
    
    # Send advertisement to main bot
    success_count = await send_ad_to_main_bot(ad_data)
    
    # Try to edit text, if fails - send new message
    try:
        await callback.message.edit_text(
            f"✅ **Рекламу підтверджено та надіслано!**\n\n"
            f"📝 Назва: {ad_data['ad_name']}\n"
            f"📊 Надіслано користувачам: {success_count}\n"
            f"🆔 ID реклами: {ad_id}"
        )
    except Exception as e:
        # If edit fails, send new message
        await callback.message.answer(
            f"✅ **Рекламу підтверджено та надіслано!**\n\n"
            f"📝 Назва: {ad_data['ad_name']}\n"
            f"📊 Надіслано користувачам: {success_count}\n"
            f"🆔 ID реклами: {ad_id}"
        )

async def reject_ad(callback: types.CallbackQuery, state: FSMContext):
    """Reject advertisement"""
    ad_id = int(callback.data.replace("reject_send_", ""))
    
    # Delete ad from database
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('DELETE FROM advertisements WHERE id = ?', (ad_id,))
    conn.commit()
    conn.close()
    
    # Try to edit text, if fails - send new message
    try:
        await callback.message.edit_text(
            f"❌ **Рекламу відхилено та видалено**\n\n"
            f"🆔 ID реклами: {ad_id}\n\n"
            f"Реклама не буде надіслана користувачам."
        )
    except Exception as e:
        # If edit fails, send new message
        await callback.message.answer(
            f"❌ **Рекламу відхилено та видалено**\n\n"
            f"🆔 ID реклами: {ad_id}\n\n"
            f"Реклама не буде надіслана користувачам."
        )

async def send_ad_to_main_bot(ad_data: dict):
    """Send advertisement to all users in main bot"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    MAIN_BOT_TOKEN = os.getenv('MAIN_BOT_TOKEN')
    
    if not MAIN_BOT_TOKEN:
        logger.error("Main bot token not found! Check MAIN_BOT_TOKEN in .env file")
        return 0
    
    logger.info(f"Starting ad broadcast to {ad_data.get('audience', 'all')} users")
    
    from aiogram import Bot
    main_bot = Bot(token=MAIN_BOT_TOKEN)
    
    # Get users based on audience selection
    conn = get_conn()
    cur = conn.cursor()
    
    audience = ad_data.get('audience', 'all')
    current_time = int(time.time())
    
    if audience == 'regular':
        # Regular users (no premium or pro) and not currently chatting
        cur.execute('''
        SELECT u.user_id FROM users u
        LEFT JOIN user_activity ua ON ua.user_id = u.user_id
        WHERE (u.premium_until IS NULL OR u.premium_until < ?)
          AND (u.pro_until IS NULL OR u.pro_until < ?)
          AND (ua.is_chatting IS NULL OR ua.is_chatting = 0)
        ''', (current_time, current_time))
    elif audience == 'premium':
        # Premium users (premium but not pro) and not currently chatting
        cur.execute('''
        SELECT u.user_id FROM users u
        LEFT JOIN user_activity ua ON ua.user_id = u.user_id
        WHERE u.premium_until > ?
          AND (u.pro_until IS NULL OR u.pro_until < ?)
          AND (ua.is_chatting IS NULL OR ua.is_chatting = 0)
        ''', (current_time, current_time))
    elif audience == 'pro':
        # PRO users and not currently chatting
        cur.execute('''
        SELECT u.user_id FROM users u
        LEFT JOIN user_activity ua ON ua.user_id = u.user_id
        WHERE u.pro_until > ?
          AND (ua.is_chatting IS NULL OR ua.is_chatting = 0)
        ''', (current_time,))
    else:
        # All users not currently chatting
        cur.execute('''
        SELECT u.user_id FROM users u
        LEFT JOIN user_activity ua ON ua.user_id = u.user_id
        WHERE (ua.is_chatting IS NULL OR ua.is_chatting = 0)
        ''')
    
    users = cur.fetchall()
    conn.close()
    
    logger.info(f"Found {len(users)} users for audience '{audience}'")
    
    # Create buttons for the ad
    ad_buttons = []
    if ad_data.get('buttons'):
        for button in ad_data['buttons']:
            ad_buttons.append([InlineKeyboardButton(text=button['name'], url=button['url'])])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=ad_buttons) if ad_buttons else None
    
    success_count = 0
    
    for user_row in users:
        user_id = user_row[0]
        try:
            # Send with media if available
            if ad_data.get('media_type') and ad_data.get('media_file_id'):
                if ad_data['media_type'] == 'photo':
                    await main_bot.send_photo(
                        chat_id=user_id,
                        photo=ad_data['media_file_id'],
                        caption=ad_data['ad_message'],
                        reply_markup=keyboard
                    )
                elif ad_data['media_type'] == 'video':
                    await main_bot.send_video(
                        chat_id=user_id,
                        video=ad_data['media_file_id'],
                        caption=ad_data['ad_message'],
                        reply_markup=keyboard
                    )
                elif ad_data['media_type'] == 'document':
                    await main_bot.send_document(
                        chat_id=user_id,
                        document=ad_data['media_file_id'],
                        caption=ad_data['ad_message'],
                        reply_markup=keyboard
                    )
            else:
                await main_bot.send_message(
                    chat_id=user_id,
                    text=ad_data['ad_message'],
                    reply_markup=keyboard
                )
            
            success_count += 1
            
        except Exception as e:
            logger.warning(f"Failed to send ad to user {user_id}: {e}")
            continue
    
    await main_bot.session.close()
    logger.info(f"Ad broadcast completed: {success_count}/{len(users)} messages sent successfully")
    return success_count

async def cancel_ad(callback: types.CallbackQuery, state: FSMContext):
    """Cancel advertisement creation"""
    await state.clear()
    
    try:
        await callback.message.edit_text(
            "❌ **Створення реклами скасовано**\n\n"
            "Всі дані видалено.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 До головного меню", callback_data="back_to_main")]
                ]
            )
        )
    except Exception:
        await callback.message.answer(
            "❌ **Створення реклами скасовано**\n\n"
            "Всі дані видалено.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 До головного меню", callback_data="back_to_main")]
                ]
            )
        )

async def main():
    """Start the admin bot"""
    try:
        # Initialize database tables
        init_admin_tables()
        init_ads_table()
        
        # Clear webhook
        await admin_bot.delete_webhook(drop_pending_updates=True)
        logger.info("Admin bot webhook cleared successfully")
        
        # Start polling
        logger.info("Starting admin bot polling...")
        await dp.start_polling(admin_bot)
        
    except Exception as e:
        logger.error(f"Error starting admin bot: {e}")
    finally:
        await admin_bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
