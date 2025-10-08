import sqlite3
import time
import asyncio
from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Import from registration module
from registration_aiogram import get_conn, get_user
from user_profile_aiogram import get_rating_text
from premium_aiogram import is_premium
import json


# Initialize chat tables
def init_chat_tables():
    """Initialize chat-related database tables"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Create waiting_users table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS waiting_users (
        user_id INTEGER PRIMARY KEY,
        search_gender TEXT,
        room_id TEXT DEFAULT 'room_general',
        join_time INTEGER DEFAULT (strftime('%s', 'now'))
    )
    ''')
    
    # Add room_id column if it doesn't exist (for existing databases)
    try:
        cur.execute('ALTER TABLE waiting_users ADD COLUMN room_id TEXT DEFAULT "room_general"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create active_chats table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS active_chats (
        user_id INTEGER,
        partner_id INTEGER,
        start_time INTEGER DEFAULT (strftime('%s', 'now')),
        PRIMARY KEY (user_id, partner_id)
    )
    ''')
    
    # Create last_partners table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS last_partners (
        user_id INTEGER,
        partner_id INTEGER,
        chat_time INTEGER,
        PRIMARY KEY (user_id, partner_id)
    )
    ''')
    
    # Create user_conversations table for admin bot
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
    
    conn.commit()
    conn.close()

# Initialize tables when module is imported
init_chat_tables()

# Conversation tracking
conversation_logs = {}  # {user_id: [messages]}

def add_message_to_log(user_id, partner_id, message_text, is_from_user=True):
    """Add message to conversation log"""
    if user_id not in conversation_logs:
        conversation_logs[user_id] = []
    
    sender = "Підозрюваний" if is_from_user else "Інкогніто"
    timestamp = time.strftime("%H:%M", time.localtime())
    
    conversation_logs[user_id].append(f"[{timestamp}] {sender}: {message_text}")
    
    # Keep only last 50 messages per conversation
    if len(conversation_logs[user_id]) > 50:
        conversation_logs[user_id] = conversation_logs[user_id][-50:]

def save_conversation_to_db(user_id, partner_id):
    """Save conversation to database for admin review"""
    if user_id not in conversation_logs or not conversation_logs[user_id]:
        return
    
    conversation_text = "\n".join(conversation_logs[user_id])
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Keep only last 3 conversations per user
    cur.execute('''
    DELETE FROM user_conversations 
    WHERE user_id = ? AND id NOT IN (
        SELECT id FROM user_conversations 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 2
    )
    ''', (user_id, user_id))
    
    # Insert new conversation
    cur.execute('''
    INSERT INTO user_conversations (user_id, partner_id, conversation_data, timestamp)
    VALUES (?, ?, ?, ?)
    ''', (user_id, partner_id, conversation_text, int(time.time())))
    
    conn.commit()
    conn.close()
    
    # Clear conversation log
    if user_id in conversation_logs:
        del conversation_logs[user_id]

# Queue management functions
def add_waiting(user_id, search_gender=None, room_id='room_general'):
    """Add user to waiting queue"""
    from rooms_system import get_user_room
    
    # Get user's current room if not specified
    if room_id == 'room_general':
        room_id = get_user_room(user_id)
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO waiting_users (user_id, search_gender, room_id) VALUES (?, ?, ?)', 
                (user_id, search_gender, room_id))
    conn.commit()
    conn.close()

def remove_waiting(user_id):
    """Remove user from waiting queue"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM waiting_users WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()

def get_waiting(search_gender=None, exclude_id=None, room_id=None):
    """Get list of waiting users in the same room"""
    from rooms_system import get_user_room
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get user's room if not specified
    if room_id is None and exclude_id:
        room_id = get_user_room(exclude_id)
    
    # Build query with room filter
    conditions = []
    params = []
    
    if room_id:
        conditions.append('room_id = ?')
        params.append(room_id)
    
    if search_gender:
        conditions.append('(search_gender IS NULL OR search_gender = ?)')
        params.append(search_gender)
    
    if exclude_id:
        conditions.append('user_id != ?')
        params.append(exclude_id)
    
    query = 'SELECT user_id FROM waiting_users'
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    cur.execute(query, params)
    waiting_users = [row[0] for row in cur.fetchall()]
    conn.close()
    return waiting_users

def is_waiting(user_id):
    """Check if user is in the waiting queue"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM waiting_users WHERE user_id=?', (user_id,))
    is_waiting = bool(cur.fetchone())
    conn.close()
    return is_waiting

# Chat connection functions
def set_active(user_id, partner_id):
    """Set active chat between two users"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO active_chats VALUES (?, ?, ?), (?, ?, ?)', 
               (user_id, partner_id, int(time.time()), partner_id, user_id, int(time.time())))
    conn.commit()
    conn.close()

def get_partner(user_id):
    """Get partner for user"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT partner_id FROM active_chats WHERE user_id=?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def remove_active(user_id):
    """Remove active chat for user"""
    conn = get_conn()
    cur = conn.cursor()
    
    # First get partner ID
    cur.execute('SELECT partner_id FROM active_chats WHERE user_id=?', (user_id,))
    row = cur.fetchone()
    partner_id = row[0] if row else None
    
    # Then remove both sides of the chat connection
    if partner_id:
        cur.execute('DELETE FROM active_chats WHERE user_id=? OR user_id=?', (user_id, partner_id))
        conn.commit()
    
    conn.close()
    return partner_id

def save_last_partner(user_id, partner_id):
    """Save last chat partner"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get chat duration
    cur.execute('SELECT start_time FROM active_chats WHERE user_id=? AND partner_id=?', (user_id, partner_id))
    row = cur.fetchone()
    start_time = row[0] if row else int(time.time())
    chat_duration = int(time.time()) - start_time
    
    cur.execute('INSERT OR REPLACE INTO last_partners VALUES (?, ?, ?)', 
               (user_id, partner_id, chat_duration))
    conn.commit()
    conn.close()

def get_last_partner(user_id):
    """Get last chat partner"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT partner_id FROM last_partners WHERE user_id=? ORDER BY chat_time DESC LIMIT 1', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# Main chat functions
async def start_search(message: types.Message):
    """Start searching for a chat partner with premium preferences if available"""
    user_id = message.from_user.id
    # Maintenance gate handled at caller level; keep function unchanged
    
    # Check if user is blocked
    from complaints_system import is_user_blocked
    if is_user_blocked(user_id):
        from bot_aiogram import send_blocked_user_message
        await send_blocked_user_message(message, "Доступ до анонімного чату заборонено")
        return
    
    # Check if already in chat first
    partner_id = get_partner(user_id)
    if partner_id:
        # Still in chat, don't change activity status to avoid false notifications
        await message.answer("Ви вже у чаті! Завершіть поточний чат перед пошуком нового співрозмовника.")
        return
    
    # Update user activity - not in chat, searching
    add_active(user_id, is_chatting=False)
    
    # Check if already searching
    if is_waiting(user_id):
        await message.answer("Ви вже шукаєте співрозмовника!")
        return
    
    # Check if user has pending return request
    from friends_system import has_pending_return_request, cancel_return_request
    if has_pending_return_request(user_id):
        # Cancel the return request and notify user
        cancel_return_request(user_id)
        await message.answer(
            "⚠️ **Увага!**\n\n"
            "З'єднання з минулим співрозмовником було відмінено, оскільки ви розпочали звичайний пошук.\n\n"
            "Щоб зупинити пошук, використайте команду /stop"
        )
    
    # Check if user has premium and preferences
    if is_premium(user_id):
        from user_profile_aiogram import get_search_preference
        
        # Get search preferences
        gender_pref = get_search_preference(user_id, 'gender')
        age_pref = get_search_preference(user_id, 'age_range')
        countries_pref = get_search_preference(user_id, 'countries')
        user_type_pref = get_search_preference(user_id, 'user_type')
        
        # If user has any preferences set, use premium search
        if any([gender_pref and gender_pref != 'any', 
                age_pref and age_pref != 'any',
                countries_pref and countries_pref != 'all',
                user_type_pref and user_type_pref != 'all']):
            await start_premium_search(message)
            return
    
    # Regular search
    add_waiting(user_id)
    search_msg = await message.answer("🔍 **Ищем собеседника...**\n\nДля остановки поиска используйте /stop")
    
    # Try to find a partner
    await search_by_user_id(user_id, message, search_msg)

async def start_premium_search(message: types.Message):
    """Start premium search with user preferences"""
    user_id = message.from_user.id
    
    # Add to waiting queue
    add_waiting(user_id)
    search_msg = await message.answer("💎 **PREMIUM поиск собеседника...**\n\nИспользуются ваши настройки поиска\nДля остановки поиска используйте /stop")
    
    # Try to find a partner with preferences
    await search_by_user_id(user_id, message, search_msg)

async def search_by_gender(message: types.Message, gender: str):
    """Search for partner by specific gender"""
    user_id = message.from_user.id
    
    # Check if already in chat
    partner_id = get_partner(user_id)
    if partner_id:
        await message.answer("Ви вже у чаті! Завершіть поточний чат перед пошуком нового співрозмовника.")
        return
    
    # Check if already searching
    if is_waiting(user_id):
        await message.answer("Ви вже шукаєте співрозмовника!")
        return
    
    # Add to waiting queue with gender preference
    search_gender = "👨 Чоловік" if gender == "male" else "👩 Жінка"
    add_waiting(user_id, search_gender)
    search_msg = await message.answer(f"🔍 **Ищем собеседника ({search_gender})...**\n\nДля остановки поиска используйте /stop")
    
    # Try to find a partner
    await search_by_user_id(user_id, message, search_msg)

async def search_by_user_id(user_id: int, message: types.Message, search_message: types.Message = None):
    """Search for a partner for specific user"""
    # First check if there are any pending return requests for this user
    from friends_system import get_pending_return_request_for_user, accept_return_request
    
    pending_return_from = get_pending_return_request_for_user(user_id)
    if pending_return_from:
        # There's a pending return request, connect them automatically
        # Remove both from waiting queue
        remove_waiting(user_id)
        remove_waiting(pending_return_from)
        
        # Accept the return request
        accept_return_request(pending_return_from, user_id)
        
        # Set active chat
        set_active(user_id, pending_return_from)
        
        # Update both users' activity as chatting
        add_active(user_id, is_chatting=True)
        add_active(pending_return_from, is_chatting=True)
        
        # Get partner info for display
        partner_data = get_user(pending_return_from)
        user_data = get_user(user_id)
        
        if partner_data and user_data:
            # Connect as normal search (no special message about return)
            await connect_users(user_id, pending_return_from, message, search_message, 
                              user_data, partner_data, is_request_connection=False)
        return
    
    # Then check if there are any pending chat requests for this user
    from friends_system import get_pending_request_for_user, accept_chat_request
    
    pending_request_from = get_pending_request_for_user(user_id)
    if pending_request_from:
        # There's a pending request from a PRO user, connect them automatically
        # Remove both from waiting queue
        remove_waiting(user_id)
        remove_waiting(pending_request_from)
        
        # Accept the request
        accept_chat_request(pending_request_from, user_id)
        
        # Set active chat
        set_active(user_id, pending_request_from)
        
        # Update both users' activity as chatting
        add_active(user_id, is_chatting=True)
        add_active(pending_request_from, is_chatting=True)
        
        # Get partner info for display
        partner_data = get_user(pending_request_from)
        user_data = get_user(user_id)
        
        if partner_data and user_data:
            await connect_users(user_id, pending_request_from, message, search_message, 
                              user_data, partner_data, is_request_connection=True)
        return
    
    # Get user's search preferences
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT search_gender FROM waiting_users WHERE user_id=?', (user_id,))
    row = cur.fetchone()
    search_gender = row[0] if row else None
    conn.close()
    
    # Find compatible partners with premium filters
    waiting_users = get_waiting(exclude_id=user_id)
    
    # Apply premium search filters if user is premium
    if is_premium(user_id):
        from user_profile_aiogram import get_search_preference
        from premium_aiogram import is_pro
        
        gender_pref = get_search_preference(user_id, 'gender')
        age_pref = get_search_preference(user_id, 'age_range')
        countries_pref = get_search_preference(user_id, 'countries')
        user_type_pref = get_search_preference(user_id, 'user_type')
        
        # Filter by user preferences
        filtered_users = []
        for potential_partner in waiting_users:
            partner_data = get_user(potential_partner)
            if not partner_data:
                continue
            
            # Gender filter
            if gender_pref and gender_pref != 'any':
                target_gender = "👨 Чоловік" if gender_pref == 'male' else "👩 Жінка"
                if partner_data['gender'] != target_gender:
                    continue
            
            # Age filter
            if age_pref and age_pref != 'any':
                partner_age = partner_data.get('age', 0)
                age_ranges = {
                    '7_17': (7, 17),
                    '18_25': (18, 25),
                    '26_35': (26, 35),
                    '36_50': (36, 50),
                    '50_plus': (50, 99)
                }
                if age_pref in age_ranges:
                    min_age, max_age = age_ranges[age_pref]
                    if not (min_age <= partner_age <= max_age):
                        continue
            
            # Country filter
            if countries_pref and countries_pref != 'all' and countries_pref:
                selected_countries = countries_pref.split(',')
                partner_country = partner_data.get('country', '')
                country_mapping = {
                    'ukraine': '🇺🇦 Україна',
                    'russia': '🇷🇺 Росія',
                    'belarus': '🇧🇾 Білорусь',
                    'english': '🇬🇧 English',
                    'other': '🌎 Решта світу'
                }
                if not any(country_mapping.get(c, c) == partner_country for c in selected_countries):
                    continue
            
            # User type filter - UPDATED LOGIC FOR PRO USERS
            if user_type_pref and user_type_pref != 'all':
                partner_is_premium = is_premium(potential_partner)
                partner_is_pro = is_pro(potential_partner)
                
                if user_type_pref == 'premium':
                    # Show only premium users, but PRO users should also appear
                    if not (partner_is_premium or partner_is_pro):
                        continue
                elif user_type_pref == 'regular':
                    # Show only regular users, but PRO users should also appear
                    if partner_is_premium and not partner_is_pro:
                        continue
            
            filtered_users.append(potential_partner)
        
        waiting_users = filtered_users
    else:
        # For non-premium users, apply basic gender filter if set
        if search_gender:
            user_data = get_user(user_id)
            user_gender = user_data['gender'] if user_data else None
            
            # Filter by gender preference
            filtered_users = []
            for potential_partner in waiting_users:
                partner_data = get_user(potential_partner)
                if partner_data and partner_data['gender'] == search_gender:
                    filtered_users.append(potential_partner)
            waiting_users = filtered_users
    
    if waiting_users:
        # Found a partner
        partner_id = waiting_users[0]
        
        # Remove both from waiting queue
        remove_waiting(user_id)
        remove_waiting(partner_id)
        
        # Set active chat
        set_active(user_id, partner_id)
        
        # Update both users' activity as chatting
        add_active(user_id, is_chatting=True)
        add_active(partner_id, is_chatting=True)
        
        # Get partner info for display
        partner_data = get_user(partner_id)
        user_data = get_user(user_id)
        
        if partner_data and user_data:
            await connect_users(user_id, partner_id, message, search_message, user_data, partner_data)

async def connect_users(user_id: int, partner_id: int, message: types.Message, 
                       search_message: types.Message = None, user_data=None, partner_data=None, 
                       is_request_connection=False):
    """Connect two users and notify them"""
    if not user_data:
        user_data = get_user(user_id)
    if not partner_data:
        partner_data = get_user(partner_id)
    
    if not (user_data and partner_data):
        return
    
    # Get partner's current ratings
    partner_rating_text = get_rating_text(partner_id)
    if not partner_rating_text:
        partner_rating_text = "⭐ **Реакции (оценка):** 0👍 0❤️ 0👎"
    else:
        partner_rating_text = f"⭐ **Реакции (оценка):** {partner_rating_text.replace('📊 Рейтинг: ', '')}"
    
    # Check if user is premium/pro to show additional details
    from premium_aiogram import is_pro
    user_is_premium = is_premium(user_id)
    user_is_pro = is_pro(user_id)
    partner_details = ""
    
    if user_is_premium or user_is_pro:
        gender_text = "Парень" if partner_data['gender'] == "👨 Чоловік" else "Девушка"
        partner_details = f"👤 **Собеседник:** {gender_text}, {partner_data['age']} лет, {partner_data['country']}"
        
        # Show ID for PRO users
        if user_is_pro:
            partner_details += f"\n🆔 **ID:** `{partner_id}`"
        
        partner_details += "\n\n"
    
    # Delete search message if it exists
    try:
        if search_message:
            await search_message.delete()
    except:
        pass  # Message might be already deleted or not deletable
    
    # Different messages for request connections vs regular connections
    if is_request_connection:
        connection_text = "🎉 **Подключен к запросу!**\n\n"
    else:
        connection_text = "🎉 **Нашел собеседника!**\n\n"
    
    # Notify both users with new format
    await message.answer(
        f"{connection_text}"
        f"💬 **Комната:** Общение\n\n"
        f"{partner_details}"
        f"{partner_rating_text}\n\n"
        f"📋 **Команды:**\n"
        f"/next - Следующий собеседник\n"
        f"/stop - Завершить чат"
    )
    
    # Notify partner
    try:
        from bot_aiogram import bot
        
        # Get user's current ratings for partner
        user_rating_text = get_rating_text(user_id)
        if not user_rating_text:
            user_rating_text = "⭐ **Реакции (оценка):** 0👍 0❤️ 0👎"
        else:
            user_rating_text = f"⭐ **Реакции (оценка):** {user_rating_text.replace('📊 Рейтинг: ', '')}"
        
        # Check if partner is premium/pro to show additional details
        from premium_aiogram import is_pro
        partner_is_premium = is_premium(partner_id)
        partner_is_pro = is_pro(partner_id)
        user_details = ""
        
        if partner_is_premium or partner_is_pro:
            gender_text = "Парень" if user_data['gender'] == "👨 Чоловік" else "Девушка"
            user_details = f"👤 **Собеседник:** {gender_text}, {user_data['age']} лет, {user_data['country']}"
            
            # Show ID for PRO users
            if partner_is_pro:
                user_details += f"\n🆔 **ID:** `{user_id}`"
            
            user_details += "\n\n"
        
        if is_request_connection:
            partner_connection_text = "🎉 **Ваш запрос принят!**\n\n"
        else:
            partner_connection_text = "🎉 **Нашел собеседника!**\n\n"
        
        await bot.send_message(
            partner_id,
            f"{partner_connection_text}"
            f"💬 **Комната:** Общение\n\n"
            f"{user_details}"
            f"{user_rating_text}\n\n"
            f"📋 **Команды:**\n"
            f"/next - Следующий собеседник\n"
            f"/stop - Завершить чат"
        )
    except Exception as e:
        print(f"Error notifying partner {partner_id}: {e}")

def format_partner_profile(user_data):
    """Format partner profile for display"""
    gender_emoji = "👨" if user_data['gender'] == "👨 Чоловік" else "👩"
    
    profile_text = f"{gender_emoji} Вік: {user_data['age']}\n"
    profile_text += f"🌍 Країна: {user_data['country']}\n"
    
    if user_data['interests']:
        profile_text += f"🔍 Інтереси: {user_data['interests']}\n"
    
    # Add rating
    rating_text = get_rating_text(user_data['user_id'])
    if rating_text:
        profile_text += f"\n{rating_text}"
    
    return profile_text

def get_rating_keyboard(partner_id):
    """Create rating keyboard for partner"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍", callback_data=f"rate_like_{partner_id}"),
                InlineKeyboardButton(text="❤️", callback_data=f"rate_love_{partner_id}"),
                InlineKeyboardButton(text="👎", callback_data=f"rate_dislike_{partner_id}")
            ],
            [InlineKeyboardButton(text="🚫 Поскаржитися", callback_data=f"report_{partner_id}")],
            [
                InlineKeyboardButton(text="🔄 Повернутися", callback_data=f"return_{partner_id}"),
                InlineKeyboardButton(text="➡️ Наступний", callback_data="next")
            ]
        ]
    )

async def stop_chat(message: types.Message):
    """Stop current chat"""
    user_id = message.from_user.id
    
    # Check if in chat
    partner_id = get_partner(user_id)
    if not partner_id:
        # Check if searching
        if is_waiting(user_id):
            remove_waiting(user_id)
            await message.answer("Пошук зупинено.")
        else:
            await message.answer("Наразі ви не у чаті та не шукаєте співрозмовника.")
        return
    
    # Stop the chat
    await stop_chat_between_users(user_id, partner_id, message)

def get_chat_end_keyboard(partner_id: int, user_status: str):
    """Get keyboard for chat end with options based on user status"""
    # Rating buttons in one row
    rating_buttons = [
        [
            InlineKeyboardButton(text="👍 Добре", callback_data=f"rate_good_{partner_id}"),
            InlineKeyboardButton(text="👎 Погано", callback_data=f"rate_bad_{partner_id}"),
            InlineKeyboardButton(text="❤️ Супер", callback_data=f"rate_super_{partner_id}")
        ],
        [InlineKeyboardButton(text="🚫 Поскаржитися", callback_data=f"report_{partner_id}")]
    ]
    
    # Add special buttons based on user status
    if user_status == 'pro':
        # PRO users get both return and add friend buttons in one row
        rating_buttons.insert(0, [
            InlineKeyboardButton(text="🔄 Повернутися", callback_data=f"return_to_{partner_id}"),
            InlineKeyboardButton(text="👥 Додати в друзі", callback_data=f"add_friend_{partner_id}")
        ])
    elif user_status == 'premium':
        # Premium users get only return button
        rating_buttons.insert(0, [InlineKeyboardButton(text="🔄 Повернутися", callback_data=f"return_to_{partner_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rating_buttons)

async def stop_chat_between_users(user_id: int, partner_id: int, message: types.Message):
    """Stop chat between two specific users"""
    # Save last partner info
    save_last_partner(user_id, partner_id)
    save_last_partner(partner_id, user_id)
    
    # Save conversations for both users before ending chat
    save_conversation_to_db(user_id, partner_id)
    save_conversation_to_db(partner_id, user_id)
    
    # Update both users' activity as not chatting
    add_active(user_id, is_chatting=False)
    add_active(partner_id, is_chatting=False)
    
    # Remove active chat
    remove_active(user_id)

    # After chat ends, process buffered conversation for media archiving
    try:
        from media_archive import process_conversation_archive
        from bot_aiogram import bot
        await process_conversation_archive(bot, user_id, partner_id)
    except Exception as e:
        print(f"Conversation archive processing failed for {user_id}-{partner_id}: {e}")
    
    # Check status for both users
    from premium_aiogram import get_user_status
    user_status = get_user_status(user_id)
    partner_status = get_user_status(partner_id)
    
    # Create rating keyboards with options based on user status
    user_rating_keyboard = get_chat_end_keyboard(partner_id, user_status)
    partner_rating_keyboard = get_chat_end_keyboard(user_id, partner_status)
    
    # Notify user with rating option
    await message.answer("✅ Ви зупинили розмову.")
    
    status_emoji = " 🌟" if user_status == 'pro' else " 💎" if user_status == 'premium' else ""
    await message.answer(
        "Оцініть вашого співрозмовника:" + status_emoji,
        reply_markup=user_rating_keyboard
    )
    
    try:
        from bot_aiogram import bot
        await bot.send_message(
            partner_id,
            "✅ Співрозмовник зупинив розмову."
        )
        # Send rating option to partner
        partner_status_emoji = " 🌟" if partner_status == 'pro' else " 💎" if partner_status == 'premium' else ""
        await bot.send_message(
            partner_id,
            "Оцініть вашого співрозмовника:" + partner_status_emoji,
            reply_markup=partner_rating_keyboard
        )
    except Exception as e:
        print(f"Error notifying partner {partner_id}: {e}")

async def forward_message(message: types.Message):
    """Forward message to chat partner"""
    user_id = message.from_user.id
    partner_id = get_partner(user_id)
    
    if not partner_id:
        await message.answer("Ви не у чаті з ким-небудь.")
        return
    
    # Check for links in first 15 seconds of chat
    if message.text:
        import re
        import time
        
        # Check if message contains links
        link_pattern = r'(https?://[^\s]+|www\.[^\s]+|[^\s]+\.[a-z]{2,}(?:/[^\s]*)?)'
        if re.search(link_pattern, message.text, re.IGNORECASE):
            # Get chat start time
            conn = get_conn()
            cur = conn.cursor()
            
            # Get when this chat started (first message between these users)
            cur.execute('''
            SELECT MIN(timestamp) FROM conversation_logs 
            WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?)
            ''', (user_id, partner_id, partner_id, user_id))
            
            result = cur.fetchone()
            conn.close()
            
            if result and result[0]:
                chat_start_time = result[0]
                current_time = int(time.time())
                
                # If chat started less than 15 seconds ago, block links
                if current_time - chat_start_time < 15:
                    await message.answer(
                        "🚫 *Посилання заборонені в перші 15 секунд чату*\n\n"
                        "Зачекайте трохи перед відправкою посилань для безпеки співрозмовника."
                    )
                    return
    
    try:
        from bot_aiogram import bot
        
        # Log message for conversation tracking
        message_text = ""
        if message.text:
            message_text = message.text
            await bot.send_message(partner_id, message.text)
        elif message.photo:
            message_text = f"[Фото] {message.caption or ''}"
            await bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
        elif message.video:
            message_text = f"[Відео] {message.caption or ''}"
            await bot.send_video(partner_id, message.video.file_id, caption=message.caption)
        elif message.audio:
            message_text = f"[Аудіо] {message.caption or ''}"
            await bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)
        elif message.voice:
            message_text = "[Голосове повідомлення]"
            await bot.send_voice(partner_id, message.voice.file_id)
        elif message.document:
            message_text = f"[Документ] {message.caption or ''}"
            await bot.send_document(partner_id, message.document.file_id, caption=message.caption)
        elif message.sticker:
            message_text = "[Стікер]"
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.animation:
            message_text = f"[GIF] {message.caption or ''}"
            await bot.send_animation(partner_id, message.animation.file_id, caption=message.caption)
        
        # Send to following admins asynchronously (non-blocking)
        import asyncio
        from admin_commands import send_message_to_following_admins
        
        # Determine message type for admin notification
        message_type = "text"
        media_info = None
        
        if message.photo:
            message_type = "photo"
            media_info = message.photo[-1].file_id
        elif message.video:
            message_type = "video"
            media_info = message.video.file_id
        elif message.audio:
            message_type = "audio"
            media_info = message.audio.file_id
        elif message.voice:
            message_type = "voice"
            media_info = message.voice.file_id
        elif message.document:
            message_type = "document"
            media_info = message.document.file_id
        elif message.sticker:
            message_type = "sticker"
            media_info = message.sticker.file_id
        elif message.animation:
            message_type = "animation"
            media_info = message.animation.file_id
        
        # Send admin notification in background (non-blocking)
        # Check if any admin is following either user in this conversation
        from admin_commands import send_message_to_following_admins_conversation
        asyncio.create_task(send_message_to_following_admins_conversation(user_id, partner_id, message_text, message_type, media_info))
        
        # Add message to conversation logs for both users (in background)
        if message_text:
            asyncio.create_task(asyncio.to_thread(add_message_to_log, user_id, partner_id, message_text, True))
            asyncio.create_task(asyncio.to_thread(add_message_to_log, partner_id, user_id, message_text, False))
        
        # Update message count and activity (in background)
        asyncio.create_task(asyncio.to_thread(update_user_stats, user_id, 1))
        asyncio.create_task(asyncio.to_thread(add_active, user_id, True))
        
    except Exception as e:
        print(f"Error forwarding message to {partner_id}: {e}")
        await message.answer("Помилка при відправці повідомлення.")

def add_active(user_id, is_chatting=False):
    """Add or update user activity - wrapper for friends_system function"""
    from friends_system import update_user_activity
    update_user_activity(user_id, is_chatting)

def update_user_stats(user_id, messages_sent=0, chats_count=0):
    """Update user statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT OR IGNORE INTO statistics (user_id, messages_sent, chats_count)
    VALUES (?, 0, 0)
    ''', (user_id,))
    
    if messages_sent > 0:
        cur.execute('''
        UPDATE statistics SET messages_sent = messages_sent + ?
        WHERE user_id = ?
        ''', (messages_sent, user_id))
    
    if chats_count > 0:
        cur.execute('''
        UPDATE statistics SET chats_count = chats_count + ?
        WHERE user_id = ?
        ''', (chats_count, user_id))
    
    conn.commit()
    conn.close()

# Initialize chat tables when module is imported
init_chat_tables()
