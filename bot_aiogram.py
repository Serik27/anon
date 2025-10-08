import asyncio
import logging
import sys
import os
import sqlite3
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import time as dt_time
import time

# Load environment variables
load_dotenv()
# Import modules
import registration_aiogram as registration
import user_profile_aiogram as profile
import premium_aiogram as premium
from premium_aiogram import is_premium, premium_menu
import chat_aiogram as chat
import callback_handler_aiogram as callback_handler
import admin_commands
from complaints_system import save_user_message, is_user_blocked
from media_archive import buffer_record_text, buffer_record_media
from maintenance import (
    is_maintenance_enabled,
    get_maintenance_message,
    get_restored_message,
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def send_blocked_user_message(message: types.Message, context_status: str = "Доступ заборонено"):
    """Send unified blocked user message with unblock button"""
    user_id = message.from_user.id
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
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
        f"🚫 *Ваш акаунт заблоковано*\n\n"
        f"📋 *Причина:* Порушення правил\n"
        f"🚫 *Статус:* {context_status}\n\n"
        f"💡 *Можливості:*\n"
        f"• Зачекати розблокування адміністратором\n"
        f"• Розблокувати негайно за 99⭐ (кнопка нижче)"
    )
    
    await message.answer(block_message, reply_markup=keyboard, parse_mode="Markdown")

# Bot and dispatcher
bot = Bot(
    token=os.getenv('MAIN_BOT_TOKEN'),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Initialize database and chat tables
registration.init_db()
chat.init_chat_tables()

# Register callback handlers
callback_handler.register_callback_handlers(dp)

# Register admin handlers
admin_commands.register_admin_handlers(dp)
# =====================
# Media archive settings
# =====================
MEDIA_ARCHIVE_CHANNEL_ID = int(os.getenv('MEDIA_ARCHIVE_CHANNEL_ID', '0') or '0')
MEDIA_DB_PATH = 'media_store.db'
FILTER_WORDS_FILE = 'filter_words.txt'

def ensure_media_db():
    conn = sqlite3.connect(MEDIA_DB_PATH)
    cur = conn.cursor()
    # Create with desired schema if not exists
    cur.execute('''
    CREATE TABLE IF NOT EXISTS saved_media (
        file_id TEXT PRIMARY KEY,
        sender_id INTEGER
    )
    ''')
    # Migrate old schema (media_type/saved_at) to new schema if needed
    try:
        cur.execute('PRAGMA table_info(saved_media)')
        cols = [row[1] for row in cur.fetchall()]
        if cols and (('media_type' in cols) or ('saved_at' in cols)):
            # Recreate table with new schema
            cur.execute('''
            CREATE TABLE IF NOT EXISTS saved_media_new (
                file_id TEXT PRIMARY KEY,
                sender_id INTEGER
            )
            ''')
            # Copy unique file_ids; sender is unknown, set NULL
            cur.execute('INSERT OR IGNORE INTO saved_media_new (file_id) SELECT DISTINCT file_id FROM saved_media')
            cur.execute('DROP TABLE saved_media')
            cur.execute('ALTER TABLE saved_media_new RENAME TO saved_media')
    except Exception:
        pass
    conn.commit()
    conn.close()

def is_media_saved(file_id: str) -> bool:
    try:
        conn = sqlite3.connect(MEDIA_DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM saved_media WHERE file_id = ?', (file_id,))
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Media DB error (is_media_saved): {e}")
        return False

def mark_media_saved(file_id: str, sender_id: int):
    try:
        conn = sqlite3.connect(MEDIA_DB_PATH)
        cur = conn.cursor()
        cur.execute('INSERT OR IGNORE INTO saved_media (file_id, sender_id) VALUES (?, ?)', (file_id, sender_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Media DB error (mark_media_saved): {e}")

def load_filter_words() -> list[str]:
    try:
        if os.path.exists(FILTER_WORDS_FILE):
            with open(FILTER_WORDS_FILE, 'r', encoding='utf-8') as f:
                return [w.strip().lower() for w in f if w.strip() and not w.strip().startswith('#')]
    except Exception as e:
        logger.warning(f"Failed to read {FILTER_WORDS_FILE}: {e}")
    # Default minimal list (edit filter_words.txt to customize)
    return []

async def maybe_archive_media(message: types.Message, media_type: str, file_id: str):
    # Only archive if caption contains any filter word
    caption = (message.caption or '').lower()
    words = load_filter_words()
    if not words:
        return  # No filters defined → skip archiving
    if not any(w in caption for w in words):
        return

    if is_media_saved(file_id):
        return

    try:
        # Send to archive channel by file_id
        if not MEDIA_ARCHIVE_CHANNEL_ID:
            return
        if media_type == 'photo':
            await bot.send_photo(MEDIA_ARCHIVE_CHANNEL_ID, photo=file_id, caption=message.caption or '')
        elif media_type == 'video':
            await bot.send_video(MEDIA_ARCHIVE_CHANNEL_ID, video=file_id, caption=message.caption or '')
        elif media_type == 'video_note':
            await bot.send_video_note(MEDIA_ARCHIVE_CHANNEL_ID, video_note=file_id)
        elif media_type == 'document':
            await bot.send_document(MEDIA_ARCHIVE_CHANNEL_ID, document=file_id, caption=message.caption or '')
        else:
            return
        # Record file as saved with sender id
        try:
            from media_archive import mark_media_saved
            mark_media_saved(file_id, message.from_user.id)
        except Exception:
            pass
        logger.info(f"Archived {media_type} to channel for file_id={file_id}")
    except Exception as e:
        logger.error(f"Failed to archive media: {e}")

# (local conversation buffer removed; using media_archive module)


# States for FSM
class RegistrationStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_country = State()

class ProfileEditStates(StatesGroup):
    editing_gender = State()
    editing_age = State()
    editing_country = State()
    waiting_for_age_input = State()

class FriendStates(StatesGroup):
    waiting_for_name = State()

# Premium search states removed - using inline buttons instead

# Global state variables
edit_profile_state = {}
user_section = {}
search_preferences = {}

# Keyboards
def get_gender_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='👨 Чоловік', callback_data='reg_gender_male')],
            [InlineKeyboardButton(text='👩 Жінка', callback_data='reg_gender_female')]
        ]
    )

def get_main_keyboard(user_id=None):
    """Get main keyboard based on user status"""
    keyboard = [
        [KeyboardButton(text='🔍 Пошук співрозмовника')],
        [KeyboardButton(text='💎 PREMIUM пошук')],
        [KeyboardButton(text='🏠 Кімнати'), KeyboardButton(text='👤 Анкета')]
    ]
    
    # Add Friends button for PRO users
    if user_id:
        from premium_aiogram import is_pro
        if is_pro(user_id):
            keyboard.append([KeyboardButton(text='👥 Друзі')])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)




def get_country_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Україна", callback_data="country_ukraine")],
            [InlineKeyboardButton(text="🇷🇺 Росія", callback_data="country_russia")],
            [InlineKeyboardButton(text="🇧🇾 Білорусь", callback_data="country_belarus")],
            [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kazakhstan")],
            [InlineKeyboardButton(text="🇬🇪 Грузія", callback_data="country_georgia")],
            [InlineKeyboardButton(text="🇪🇺 Європа", callback_data="country_europe")],
            [InlineKeyboardButton(text="🇦🇿 Азербайджан", callback_data="country_azerbaijan")],
            [InlineKeyboardButton(text="🇺🇿 Узбекистан", callback_data="country_uzbekistan")],
            [InlineKeyboardButton(text="🇺🇸 США", callback_data="country_usa")],
            [InlineKeyboardButton(text="🇹🇭 Тайланд", callback_data="country_thailand")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="country_english")],
            [InlineKeyboardButton(text="🌎 Решта світу", callback_data="country_other")]
        ]
    )


def get_premium_offer_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💎 Отримати Преміум", callback_data="get_premium")]]
    )

# Command handlers
@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Update user info
    registration.update_user_info(user_id, username, first_name)
    
    # Check if user is blocked
    from complaints_system import is_user_blocked
    if is_user_blocked(user_id):
        await send_blocked_user_message(message, "Доступ до бота заборонено")
        return
    
    # Check required channel subscriptions
    from complaints_system import check_user_subscriptions, create_subscription_keyboard
    is_subscribed = await check_user_subscriptions(user_id, bot)
    
    if not is_subscribed:
        keyboard = create_subscription_keyboard()
        if keyboard:
            await message.answer(
                "📺 **Обов'язкова підписка**\n\n"
                "Для використання бота потрібно підписатися на наші канали:\n\n"
                "👇 Натисніть на кнопки нижче та підпишіться:",
                reply_markup=keyboard
            )
            return
    
    # Check if user is registered
    user_data = registration.get_user(user_id)
    
    if user_data:
        # If maintenance enabled, show banner on /start
        if is_maintenance_enabled():
            try:
                await message.answer(get_maintenance_message())
            except Exception:
                pass
        # Update user info if needed
        if not user_data.get('username') or not user_data.get('first_name'):
            registration.update_user_field(user_id, 'username', message.from_user.username)
            registration.update_user_field(user_id, 'first_name', message.from_user.first_name)
        
        # User already registered - show restart message
        await message.answer(
            f"🔄 **Бот перезапущен!**\n\n"
            f"Привіт, {user_data.get('first_name', 'друг')}!\n\n"
            f"Натисніть /search, щоб шукати співрозмовника.",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        # New user - start registration
        await message.answer(
            "Ласкаво просимо в бот анонімного чату! Для початку потрібно заповнити профіль.\n\n1. Оберіть вашу стать:",
            reply_markup=get_gender_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_gender)

@dp.message(Command("stop"))
async def stop_command(message: types.Message):
    """Handle /stop command"""
    await chat.stop_chat(message)

@dp.message(Command("search"))
async def search_command(message: types.Message):
    """Handle /search command - start searching for a chat partner"""
    user_id = message.from_user.id
    # Maintenance gate
    try:
        if is_maintenance_enabled():
            await message.answer(get_maintenance_message())
            return
    except Exception:
        pass
    
    # Check if user is blocked
    from complaints_system import is_user_blocked
    if is_user_blocked(user_id):
        await send_blocked_user_message(message, "Доступ до пошуку заборонено")
        return
    
    # Check required channel subscriptions
    from complaints_system import check_user_subscriptions, create_subscription_keyboard
    is_subscribed = await check_user_subscriptions(user_id, bot)
    
    if not is_subscribed:
        keyboard = create_subscription_keyboard()
        if keyboard:
            await message.answer(
                "📺 **Потрібна підписка**\n\n"
                "Для пошуку співрозмовника потрібно підписатися на наші канали:",
                reply_markup=keyboard
            )
            return
    
    # Check if user is registered
    user_data = registration.get_user(user_id)
    if not user_data:
        await message.answer("Спочатку потрібно зареєструватися. Натисніть /start")
        return
    
    # Check if already in chat
    partner_id = chat.get_partner(user_id)
    if partner_id:
        await message.answer("Ви вже у чаті! Використайте /stop щоб завершити поточний чат.")
        return
    
    # Check if already searching
    if chat.is_waiting(user_id):
        await message.answer("Ви вже шукаєте співрозмовника!")
        return
    
    # Start search
    chat.add_waiting(user_id)
    search_msg = await message.answer("🔍 **Ищем собеседника...**\n\nДля остановки поиска используйте /stop")
    await chat.search_by_user_id(user_id, message, search_msg)

@dp.message(Command("next"))
async def next_command(message: types.Message):
    """Handle /next command"""
    user_id = message.from_user.id
    # Maintenance gate
    try:
        if is_maintenance_enabled():
            await message.answer(get_maintenance_message())
            return
    except Exception:
        pass
    
    # Check if user is registered
    user_data = registration.get_user(user_id)
    if not user_data:
        await message.answer("Спочатку потрібно зареєструватися. Натисніть /start")
        return
    
    partner_id = chat.get_partner(user_id)
    
    if partner_id:
        # End current chat and start new search
        await chat.stop_chat_between_users(user_id, partner_id, message)
        # Add small delay before starting new search
        import asyncio
        await asyncio.sleep(1)
    
    # Check if already searching
    if chat.is_waiting(user_id):
        await message.answer("Ви вже шукаєте співрозмовника!")
        return
    
    # Start new search (works even without active chat)
    chat.add_waiting(user_id)
    search_msg = await message.answer("🔍 **Ищем собеседника...**\n\nДля остановки поиска используйте /stop")
    await chat.search_by_user_id(user_id, message, search_msg)

# Registration handlers - now handled by callback

@dp.message(StateFilter(RegistrationStates.waiting_for_age))
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not 7 <= age <= 99:
            await message.answer("Будь ласка, введіть коректний вік (від 7 до 99 років):")
            return
        
        await state.update_data(age=age)
        await state.set_state(RegistrationStates.waiting_for_country)
        await message.answer("3. Оберіть вашу країну:", reply_markup=get_country_keyboard())
        
    except ValueError:
        await message.answer("Будь ласка, введіть коректний вік (тільки цифри):")

# Callback query handlers are now handled in callback_handler_aiogram.py

# Profile edit age handler
@dp.message(StateFilter(ProfileEditStates.waiting_for_age_input))
async def process_age_edit(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not 7 <= age <= 99:
            await message.answer("Будь ласка, введіть коректний вік (від 7 до 99 років):")
            return
        
        user_id = message.from_user.id
        profile.update_user_age(user_id, age)
        
        await message.answer(f"✅ Вік змінено на {age} років")
        
        # Show updated profile
        profile_text = profile.format_combined_profile(user_id, is_premium)
        await message.answer(profile_text, reply_markup=profile.get_profile_edit_inline_keyboard())
        
        await state.clear()
        
    except ValueError:
        await message.answer("Будь ласка, введіть коректний вік (тільки цифри):")

# Premium search age range is now handled by inline buttons



# Main menu handlers
@dp.message(F.text == "🔍 Пошук співрозмовника")
async def search_partner(message: types.Message):
    # Maintenance gate
    try:
        if is_maintenance_enabled():
            await message.answer(get_maintenance_message())
            return
    except Exception:
        pass
    await chat.start_search(message)



@dp.message(F.text == "💎 PREMIUM пошук")
async def premium_search(message: types.Message):
    user_id = message.from_user.id
    from premium_aiogram import is_premium
    if not is_premium(user_id):
        # Відразу відкриваємо меню покупки преміум
        from premium_aiogram import premium_menu
        await premium_menu(message)
        return
    
    # Show premium search and settings combined
    await message.answer(
        profile.get_search_preferences_text(user_id),
        reply_markup=profile.get_search_settings_keyboard(user_id)
    )

@dp.message(F.text == "👤 Анкета")
async def show_profile_combined(message: types.Message):
    user_id = message.from_user.id
    
    # Get combined profile and statistics
    from premium_aiogram import is_premium
    profile_text = profile.format_combined_profile(user_id, is_premium)
    
    await message.answer(profile_text, reply_markup=profile.get_profile_edit_inline_keyboard())

def get_rooms_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Общение", callback_data="room_general")],
            [InlineKeyboardButton(text="🔞 Обмен 18+", callback_data="room_exchange")],
            [InlineKeyboardButton(text="🏳️‍🌈 ЛГБТ", callback_data="room_lgbt")],
            [InlineKeyboardButton(text="🎓 Школа", callback_data="room_school")]
        ]
    )

@dp.message(F.text == "🏠 Кімнати")
async def show_rooms_menu(message: types.Message):
    await message.answer(
        "🏠 **Оберіть кімнату для спілкування:**\n\n"
        "💬 **Общение** - загальне спілкування\n"
        "🔞 **Обмен 18+** - для дорослих\n"
        "🏳️‍🌈 **ЛГБТ** - ЛГБТ спільнота\n"
        "🎓 **Школа** - для школярів",
        reply_markup=get_rooms_keyboard()
    )

# Temporary command for testing referrals (REMOVE IN PRODUCTION)
@dp.message(Command("test_referrals"))
async def test_referrals_command(message: types.Message):
    """Add test referrals for debugging"""
    user_id = message.from_user.id
    
    from premium_aiogram import add_test_referrals, get_referral_count
    
    # Add 5 test referrals
    add_test_referrals(user_id, 5)
    
    # Check current count
    count = get_referral_count(user_id)
    
    await message.answer(f"✅ Додано 5 тестових рефералів!\n\nЗагальна кількість: {count}")

# Temporary command for testing referrals (REMOVE IN PRODUCTION)
@dp.message(Command("test_referrals_10"))
async def test_referrals_10_command(message: types.Message):
    """Add 10 test referrals for debugging"""
    user_id = message.from_user.id
    
    from premium_aiogram import add_test_referrals, get_referral_count
    
    # Add 10 test referrals
    add_test_referrals(user_id, 10)
    
    # Check current count
    count = get_referral_count(user_id)
    
    await message.answer(f"✅ Додано 10 тестових рефералів!\n\nЗагальна кількість: {count}")

# Temporary command for clearing used rewards (REMOVE IN PRODUCTION)
@dp.message(Command("clear_rewards"))
async def clear_rewards_command(message: types.Message):
    """Clear used rewards for debugging"""
    user_id = message.from_user.id
    
    from premium_aiogram import get_conn
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Clear used rewards for this user
    cur.execute('DELETE FROM referral_rewards WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await message.answer("✅ Використані нагороди очищено!")



@dp.message(F.text == "🛑 Зупинити пошук")
async def stop_search(message: types.Message):
    user_id = message.from_user.id
    chat.remove_waiting(user_id)
    await message.answer("Пошук зупинено.", reply_markup=get_main_keyboard(user_id))

@dp.message(F.text == "🛑 Зупинити")
async def stop_chat(message: types.Message):
    await chat.stop_chat(message)

@dp.message(F.text == "👥 Друзі")
async def friends_menu(message: types.Message):
    """Handle Friends button"""
    from friends_system import show_friends_list
    await show_friends_list(message)

@dp.message(Command("add_friends"))
async def add_friends_command(message: types.Message, state: FSMContext):
    """Handle /add_friends command"""
    user_id = message.from_user.id
    
    # Check PRO status
    from premium_aiogram import is_pro, send_pro_required_message
    if not is_pro(user_id):
        await send_pro_required_message(message, "команда /add_friends")
        return
    
    from friends_system import handle_add_friends_command
    await handle_add_friends_command(message, state)

@dp.message(Command("friends"))
async def friends_command(message: types.Message):
    """Handle /friends command"""
    user_id = message.from_user.id
    
    # Check PRO status
    from premium_aiogram import is_pro, send_pro_required_message
    if not is_pro(user_id):
        await send_pro_required_message(message, "команда /friends")
        return
    
    from friends_system import handle_friends_command
    await handle_friends_command(message)

@dp.message(Command("premium"))
async def premium_command(message: types.Message):
    """Handle /premium command - show premium purchase menu"""
    await premium_menu(message)

@dp.message(Command("pro"))
async def pro_command(message: types.Message):
    """Handle /pro command - show PRO features menu"""
    user_id = message.from_user.id
    
    # Check PRO status
    from premium_aiogram import is_pro, send_pro_required_message
    if not is_pro(user_id):
        await send_pro_required_message(message, "команда /pro")
        return
    
    # Create PRO features keyboard
    pro_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Мої друзі", callback_data="pro_friends")],
            [InlineKeyboardButton(text="🌟 Про PRO статус", callback_data="pro_about")]
        ]
    )
    
    # Get user's PRO info
    from premium_aiogram import get_user_status
    from registration_aiogram import get_conn
    import time
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    pro_until = row[0] if row else 0
    conn.close()
    
    # Calculate remaining time
    current_time = int(time.time())
    remaining_seconds = pro_until - current_time
    
    if remaining_seconds > 0:
        days = remaining_seconds // (24 * 3600)
        hours = (remaining_seconds % (24 * 3600)) // 3600
        
        if days > 0:
            time_left = f"{days} дн. {hours} год."
        else:
            time_left = f"{hours} год."
    else:
        time_left = "Назавжди"
    
    # Get friends count
    from friends_system import get_friends_list
    friends, total_count = get_friends_list(user_id, 0, 1000)  # Get all friends for count
    
    # Get active users statistics by gender
    conn = get_conn()
    cur = conn.cursor()
    
    # Get active users (last activity within 5 minutes)
    current_time = int(time.time())
    active_threshold = current_time - 300  # 5 minutes
    
    cur.execute('''
    SELECT u.gender, COUNT(*) 
    FROM users u 
    JOIN user_activity ua ON u.user_id = ua.user_id 
    WHERE ua.last_activity > ? 
    GROUP BY u.gender
    ''', (active_threshold,))
    
    active_stats = dict(cur.fetchall())
    conn.close()
    
    # Format gender statistics
    active_males = active_stats.get('👨 Чоловік', 0)
    active_females = active_stats.get('👩 Жінка', 0)
    total_active = active_males + active_females
    
    pro_text = (
        f"🌟 *PRO Панель управління*\n\n"
        f"Вітаємо в розділі PRO користувача!\n\n"
        f"📊 *Ваш PRO статус:*\n"
        f"⏰ Залишилось: {time_left}\n"
        f"👥 Друзів додано: {total_count}\n\n"
        f"📈 *Активні користувачі зараз:*\n"
        f"👨 Чоловіків: {active_males}\n"
        f"👩 Жінок: {active_females}\n"
        f"🔥 Всього активних: {total_active}\n\n"
        f"Виберіть дію з меню нижче:"
    )
    
    await message.answer(pro_text, reply_markup=pro_keyboard)

# Friend name input handler - must be before general message handler
@dp.message(StateFilter(FriendStates.waiting_for_name))
async def handle_friend_name_input(message: types.Message, state: FSMContext):
    """Handle friend name input"""
    user_id = message.from_user.id
    friend_name = message.text.strip()
    
    logger.info(f"Processing friend name input from user {user_id}: '{friend_name}'")
    
    if len(friend_name) > 50:
        await message.answer("❌ Ім'я занадто довге. Максимум 50 символів.")
        return
    
    if len(friend_name) < 1:
        await message.answer("❌ Введіть ім'я для друга.")
        return
    
    # Get friend_id from state
    data = await state.get_data()
    friend_id = data.get('adding_friend_id')
    
    if not friend_id:
        await message.answer("❌ Помилка. Спробуйте ще раз.")
        await state.clear()
        return
    
    # Add friend
    from friends_system import add_friend
    success, message_text = add_friend(user_id, friend_id, friend_name)
    
    if success:
        await message.answer(f"✅ {message_text}\n\n👤 **{friend_name}** додано до списку друзів!")
    else:
        await message.answer(f"❌ {message_text}")
    
    await state.clear()
    logger.info(f"Friend name processing completed for user {user_id}")



# Payment handlers
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Handle pre-checkout for Telegram Stars payments"""
    if pre_checkout_query.invoice_payload == "reset_ratings":
        await pre_checkout_query.answer(ok=True)
    elif pre_checkout_query.invoice_payload == "unblock_account":
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(ok=False, error_message="Невідомий товар")

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Handle successful payment"""
    if message.successful_payment.invoice_payload == "reset_ratings":
        user_id = message.from_user.id
        from user_profile_aiogram import reset_user_ratings
        reset_user_ratings(user_id)
        await message.answer("✅ Ваши оцінки успішно обнулені!")
    elif message.successful_payment.invoice_payload == "unblock_account":
        user_id = message.from_user.id
        
        # Unblock user
        from complaints_system import unblock_user
        unblock_user(user_id)
        
        await message.answer(
            "🎉 **Акаунт успішно розблокований!**\n\n"
            "✅ **Оплата прийнята:** 99⭐\n"
            "🔓 **Статус:** Розблокований\n\n"
            "💡 **Нагадування:**\n"
            "• Дотримуйтесь правил спільноти\n"
            "• Будьте ввічливими з іншими користувачами\n\n"
            "🚀 **Ласкаво просимо назад! Можете продовжувати користуватися ботом.**"
        )

# Handle all other messages (chat forwarding)
@dp.message()
async def handle_all_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    # Auto-update user info if changed
    from registration_aiogram import update_user_info
    update_user_info(user_id, message.from_user.username, message.from_user.first_name)
    
    logger.info(f"General message handler triggered for user {user_id}, state: {current_state}, text: '{message.text}'")
    
    # Skip if user is in any FSM state - let specific handlers process it
    if current_state is not None:
        logger.info(f"User {user_id} is in state {current_state}, skipping general handler")
        return
    
    # Check if user is registered
    user_data = registration.get_user(user_id)
    if not user_data:
        await message.answer("Спочатку потрібно зареєструватися. Натисніть /start")
        return
    
    # Log user activity for hourly statistics
    from admin_commands import log_user_activity
    log_user_activity(user_id)
    
    # Save user message to database for complaints system
    from complaints_system import save_user_message, is_user_blocked
    
    # Check if user is blocked
    if is_user_blocked(user_id):
        await send_blocked_user_message(message, "Доступ до анонімного чату заборонено")
        return
    
    partner_id = chat.get_partner(user_id)
    if partner_id:
        # Save message to database
        message_text = message.text if message.text else None
        media_type = None
        media_file_id = None
        
        # Check for media
        if message.photo:
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
        elif message.video:
            media_type = "video"
            media_file_id = message.video.file_id
        elif message.document:
            media_type = "document"
            media_file_id = message.document.file_id
        elif message.voice:
            media_type = "voice"
            media_file_id = message.voice.file_id
        elif message.video_note:
            media_type = "video_note"
            media_file_id = message.video_note.file_id
        elif message.sticker:
            media_type = "sticker"
            media_file_id = message.sticker.file_id
        elif message.animation:
            media_type = "animation"
            media_file_id = message.animation.file_id
        
        save_user_message(user_id, message_text, media_type, media_file_id, partner_id)
        # Buffer text/media for post-chat archiving
        try:
            if message_text is not None:
                buffer_record_text(user_id, partner_id, message_text)
            if media_type in ("photo", "video", "video_note") and media_file_id:
                buffer_record_media(user_id, partner_id, media_type, media_file_id, message.caption if hasattr(message, 'caption') else None)
        except Exception as e:
            logger.debug(f"buffer record error: {e}")
        
        # Forward message to partner
        logger.info(f"Forwarding message from {user_id} to partner {partner_id}")
        await chat.forward_message(message)

        # Immediate archiving removed; handled after chat ends via buffer
    else:
        # Default response
        await message.answer(
            "Оберіть дію з меню або натисніть 🔍 Пошук співрозмовника",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

# Callback handlers are registered in callback_handler_aiogram.py

# Register payment handlers
@dp.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    # Inline handler for precheckout (Telegram Stars)
    await pre_checkout_handler(pre_checkout_query)

@dp.message(F.successful_payment)
async def handle_successful_payment(message: types.Message):
    await successful_payment_handler(message)

# Helper functions
async def process_referral(referrer_id, referred_id):
    """Process referral and give premium if needed"""
    if referrer_id == referred_id:
        logger.info(f"User {referrer_id} tried to refer themselves")
        return
    
    # Check if referred user is new
    conn = registration.get_conn()
    cur = conn.cursor()
    
    # Check if this referral was already processed
    cur.execute('SELECT 1 FROM referrals WHERE referrer_id=? AND referred_id=?', (referrer_id, referred_id))
    if cur.fetchone():
        conn.close()
        return
    
    # Add referral to database
    cur.execute('INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?, ?, ?)', 
               (referrer_id, referred_id, int(time.time())))
    
    # Count total referrals for this user
    cur.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id=?', (referrer_id,))
    total_referrals = cur.fetchone()[0]
    
    # Give premium based on referral count
    premium_given = False
    premium_days = 0
    
    if total_referrals % 10 == 0:  # Every 10 referrals
        # Give 30 days premium
        cur.execute('SELECT premium_until FROM users WHERE user_id=?', (referrer_id,))
        row = cur.fetchone()
        current_until = row[0] if row and row[0] else 0
        now = int(time.time())
        new_until = max(now, current_until) + (30 * 24 * 3600)  # 30 days
        
        cur.execute('UPDATE users SET premium_until=? WHERE user_id=?', (new_until, referrer_id))
        logger.info(f"User {referrer_id} got 30 days premium for {total_referrals} referrals")
        premium_given = True
        premium_days = 30
    elif total_referrals % 5 == 0:  # Every 5 referrals
        # Give 7 days premium
        cur.execute('SELECT premium_until FROM users WHERE user_id=?', (referrer_id,))
        row = cur.fetchone()
        current_until = row[0] if row and row[0] else 0
        now = int(time.time())
        new_until = max(now, current_until) + (7 * 24 * 3600)  # 7 days
        
        cur.execute('UPDATE users SET premium_until=? WHERE user_id=?', (new_until, referrer_id))
        logger.info(f"User {referrer_id} got 7 days premium for {total_referrals} referrals")
        premium_given = True
        premium_days = 7
    
    conn.commit()
    conn.close()
    
    # Send notification to referrer
    try:
        if premium_given:
            await bot.send_message(
                referrer_id,
                f"🎉 **Вітаємо!**\n\n"
                f"Ви запросили {total_referrals} друзів і отримали **{premium_days} днів преміуму** безкоштовно! 💎\n\n"
                f"Продовжуйте запрошувати друзів для отримання додаткових бонусів!"
            )
        else:
            await bot.send_message(
                referrer_id,
                f"👥 **Новий друг приєднався!**\n\n"
                f"Загалом запрошено: **{total_referrals}** друзів\n"
                f"До наступної нагороди: **{5 - (total_referrals % 5)}** друзів"
            )
    except Exception as e:
        logger.error(f"Failed to send referral notification to {referrer_id}: {e}")

# Room management commands (admin only)
@dp.message(F.text.startswith("/close_room"))
async def close_room_command(message: types.Message):
    """Close room command - admin only"""
    user_id = message.from_user.id
    
    # Check if user is admin
    from admin_commands import is_admin
    if not is_admin(user_id):
        await message.answer("❌ Ця команда доступна тільки адміністраторам.")
        return
    
    # Parse command
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "❌ Неправильний формат команди.\n\n"
            "*Використання:* `/close_room room_id`\n\n"
            "*Доступні кімнати:*\n"
            "• `room_general` - 💬 Общение\n"
            "• `room_exchange` - 🔞 Обмен 18+\n"
            "• `room_lgbt` - 🏳️‍🌈 ЛГБТ\n"
            "• `room_school` - 🎓 Школа"
        )
        return
    
    room_id = parts[1]
    
    # Validate room ID
    valid_rooms = {
        "room_general": "💬 Общение",
        "room_exchange": "🔞 Обмен 18+",
        "room_lgbt": "🏳️‍🌈 ЛГБТ",
        "room_school": "🎓 Школа"
    }
    
    if room_id not in valid_rooms:
        await message.answer("❌ Невідома кімната. Використовуйте один з доступних ID.")
        return
    
    if room_id == "room_general":
        await message.answer("❌ Неможливо закрити головну кімнату 'Общение'.")
        return
    
    # Close room
    from rooms_system import close_room, is_room_open
    
    if not is_room_open(room_id):
        await message.answer(f"❌ Кімната '{valid_rooms[room_id]}' вже закрита.")
        return
    
    moved_count = close_room(room_id, user_id)
    room_name = valid_rooms[room_id]
    
    await message.answer(
        f"✅ *Кімната закрита*\n\n"
        f"🚫 Кімната: {room_name}\n"
        f"👥 Користувачів переведено в 'Общение': {moved_count}\n"
        f"👮‍♂️ Закрив: Адміністратор"
    )

@dp.message(F.text.startswith("/open_room"))
async def open_room_command(message: types.Message):
    """Open room command - admin only"""
    user_id = message.from_user.id
    
    # Check if user is admin
    from admin_commands import is_admin
    if not is_admin(user_id):
        await message.answer("❌ Ця команда доступна тільки адміністраторам.")
        return
    
    # Parse command
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "❌ Неправильний формат команди.\n\n"
            "*Використання:* `/open_room room_id`\n\n"
            "*Доступні кімнати:*\n"
            "• `room_general` - 💬 Общение\n"
            "• `room_exchange` - 🔞 Обмен 18+\n"
            "• `room_lgbt` - 🏳️‍🌈 ЛГБТ\n"
            "• `room_school` - 🎓 Школа"
        )
        return
    
    room_id = parts[1]
    
    # Validate room ID
    valid_rooms = {
        "room_general": "💬 Общение",
        "room_exchange": "🔞 Обмен 18+",
        "room_lgbt": "🏳️‍🌈 ЛГБТ",
        "room_school": "🎓 Школа"
    }
    
    if room_id not in valid_rooms:
        await message.answer("❌ Невідома кімната. Використовуйте один з доступних ID.")
        return
    
    # Open room
    from rooms_system import open_room, is_room_open
    
    if is_room_open(room_id):
        await message.answer(f"❌ Кімната '{valid_rooms[room_id]}' вже відкрита.")
        return
    
    open_room(room_id, user_id)
    room_name = valid_rooms[room_id]
    
    await message.answer(
        f"✅ *Кімната відкрита*\n\n"
        f"🟢 Кімната: {room_name}\n"
        f"👮‍♂️ Відкрив: Адміністратор"
    )

async def main():
    """Start the bot"""
    try:
        # Initialize database
        registration.init_db()
        
        # Clear webhook before starting polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared successfully")
        
        # Start activity notification scheduler
        from activity_notifications import start_activity_notification_scheduler
        asyncio.create_task(start_activity_notification_scheduler())
        logger.info("Activity notification scheduler started")
        
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        # Graceful shutdown
        logger.info("Shutting down bot...")
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
