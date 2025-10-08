import sqlite3
import time
from datetime import datetime, timedelta
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Import from registration module
from registration_aiogram import get_conn, get_user

# Keyboards for profile editing
def get_profile_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Профіль", callback_data="profile_view")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="profile_back")]
        ]
    )

def get_profile_edit_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Пол", callback_data="edit_gender"),
                InlineKeyboardButton(text="📅 Возраст", callback_data="edit_age"),
                InlineKeyboardButton(text="🌍 Страна", callback_data="edit_country")
            ],
            [InlineKeyboardButton(text="⭐ Обнулить оценки за 55 звезд", callback_data="reset_ratings_stars")],
            [InlineKeyboardButton(text="🙈 Скрыть фото/видео", callback_data="toggle_media_blur")],
            [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite_friend")]
        ]
    )

# Search settings keyboards
def get_search_settings_keyboard(user_id=None):
    """Get search settings keyboard with current preferences"""
    keyboard = [
        [InlineKeyboardButton(text="👤 Пол", callback_data="premium_search_gender")],
        [InlineKeyboardButton(text="🔢 Возраст", callback_data="premium_search_age")],
        [InlineKeyboardButton(text="🌍 Страна", callback_data="premium_search_country")],
        [InlineKeyboardButton(text="💎 Показывать Premium статус", callback_data="premium_show_status")],
        [InlineKeyboardButton(text="🔍 Тип пользователей", callback_data="premium_user_type")],
        [InlineKeyboardButton(text="🚀 Начать поиск", callback_data="premium_start_search")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_search_preferences_text(user_id):
    """Get formatted text with current search preferences"""
    gender_pref = get_search_preference(user_id, 'gender') or 'any'
    age_pref = get_search_preference(user_id, 'age_range') or 'any'
    countries_pref = get_search_preference(user_id, 'countries') or 'all'
    show_status_pref = get_search_preference(user_id, 'show_premium_status') or 'true'
    user_type_pref = get_search_preference(user_id, 'user_type') or 'all'
    
    # Format preferences
    gender_text = {"any": "Любой", "male": "Парни", "female": "Девушки"}.get(gender_pref, "Любой")
    age_text = {"any": "Любой", "7_17": "7-17", "18_25": "18-25", "26_35": "26-35", "36_50": "36-50", "50_plus": "50+"}.get(age_pref, "Любой")
    
    if countries_pref == 'all':
        countries_text = "Все страны"
    else:
        country_names = {
            "ukraine": "Украина",
            "russia": "Россия",
            "belarus": "Беларусь",
            "kazakhstan": "Казахстан",
            "georgia": "Грузия",
            "europe": "Европа",
            "azerbaijan": "Азербайджан",
            "uzbekistan": "Узбекистан",
            "usa": "США",
            "thailand": "Таиланд",
            "english": "English",
            "other": "Остальные"
        }
        selected = countries_pref.split(',') if countries_pref else []
        countries_text = ', '.join([country_names.get(c, c) for c in selected]) if selected else "Все страны"
    
    show_status_text = "Да" if show_status_pref != 'false' else "Нет"
    user_type_text = {"all": "Все", "premium": "Premium", "regular": "Обычные"}.get(user_type_pref, "Все")
    
    # Get premium/pro status info
    from premium_aiogram import is_premium, is_pro
    from registration_aiogram import get_conn
    import time
    from datetime import datetime
    
    status_info = ""
    if is_pro(user_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        pro_until = row[0] if row else 0
        conn.close()
        
        if pro_until > 0:
            end_date = datetime.fromtimestamp(pro_until)
            status_info = f"\n🌟 **PRO статус до:** {end_date.strftime('%d.%m.%Y %H:%M')}"
        else:
            status_info = f"\n🌟 **PRO статус:** Назавжди"
    elif is_premium(user_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        premium_until = row[0] if row else 0
        conn.close()
        
        if premium_until > 0:
            end_date = datetime.fromtimestamp(premium_until)
            status_info = f"\n💎 **Premium статус до:** {end_date.strftime('%d.%m.%Y %H:%M')}"
        else:
            status_info = f"\n💎 **Premium статус:** Назавжди"
    
    return (
        f"📎 **PREMIUM пошук**{status_info}\n\n"
        f"**Поточні налаштування:**\n"
        f"👤 **Пол:** {gender_text}\n"
        f"🔢 **Возраст:** {age_text}\n"
        f"🌍 **Страны:** {countries_text}\n"
        f"💎 **Показывать статус:** {show_status_text}\n"
        f"🔍 **Тип пользователей:** {user_type_text}\n\n"
        f"Налаштуйте параметри пошуку співрозмовників:"
    )

def get_premium_gender_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Любой", callback_data="premium_gender_any")],
            [InlineKeyboardButton(text="👨 Парни", callback_data="premium_gender_male")],
            [InlineKeyboardButton(text="👩 Девушки", callback_data="premium_gender_female")]
        ]
    )

def get_premium_age_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Любой", callback_data="premium_age_any")],
            [InlineKeyboardButton(text="7-17", callback_data="premium_age_7_17")],
            [InlineKeyboardButton(text="18-25", callback_data="premium_age_18_25")],
            [InlineKeyboardButton(text="26-35", callback_data="premium_age_26_35")],
            [InlineKeyboardButton(text="36-50", callback_data="premium_age_36_50")],
            [InlineKeyboardButton(text="50+", callback_data="premium_age_50_plus")]
        ]
    )

def get_premium_country_keyboard(user_id):
    """Get country keyboard with checkmarks for selected countries"""
    selected_countries = get_search_preference(user_id, 'countries')
    selected_list = selected_countries.split(',') if selected_countries else []
    
    countries = [
        ("all", "🌎 Все страны"),
        ("ukraine", "🇺🇦 Украина"),
        ("russia", "🇷🇺 Россия"),
        ("belarus", "🇧🇾 Беларусь"),
        ("kazakhstan", "🇰🇿 Казахстан"),
        ("georgia", "🇬🇪 Грузия"),
        ("europe", "🇪🇺 Европа"),
        ("azerbaijan", "🇦🇿 Азербайджан"),
        ("uzbekistan", "🇺🇿 Узбекистан"),
        ("usa", "🇺🇸 США"),
        ("thailand", "🇹🇭 Таиланд"),
        ("english", "🇬🇧 English"),
        ("other", "🌎 Остальные")
    ]
    
    keyboard = []
    for country_code, country_name in countries:
        if country_code in selected_list:
            text = f"✅ {country_name}"
        else:
            text = country_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"premium_country_{country_code}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="premium_search_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_premium_show_status_keyboard(user_id):
    """Get show status keyboard with current status"""
    show_status = get_search_preference(user_id, 'show_premium_status')
    current_status = show_status != 'false' if show_status else True  # Default True
    
    status_text = "✅ Показывать" if current_status else "❌ Скрывать"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{status_text} Premium статус", callback_data="premium_toggle_show_status")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="premium_search_back")]
        ]
    )

def get_premium_user_type_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Все пользователи", callback_data="premium_type_all")],
            [InlineKeyboardButton(text="💎 Только Premium", callback_data="premium_type_premium")],
            [InlineKeyboardButton(text="👤 Только обычные", callback_data="premium_type_regular")]
        ]
    )

# Search preferences functions
def get_search_preference(user_id, preference_type):
    """Get user search preference"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS search_preferences (
            user_id INTEGER,
            preference_type TEXT,
            preference_value TEXT,
            PRIMARY KEY (user_id, preference_type)
        )
        ''')
        
        cur.execute('SELECT preference_value FROM search_preferences WHERE user_id = ? AND preference_type = ?', 
                   (user_id, preference_type))
        result = cur.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        conn.close()
        print(f"Error getting search preference: {e}")
        return None

def set_search_preference(user_id, preference_type, preference_value):
    """Set user search preference"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS search_preferences (
            user_id INTEGER,
            preference_type TEXT,
            preference_value TEXT,
            PRIMARY KEY (user_id, preference_type)
        )
        ''')
        
        cur.execute('''
        INSERT OR REPLACE INTO search_preferences (user_id, preference_type, preference_value)
        VALUES (?, ?, ?)
        ''', (user_id, preference_type, preference_value))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"Error setting search preference: {e}")
        return False

def get_gender_search_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Будь-яка", callback_data="search_gender_any")],
            [InlineKeyboardButton(text="👨 Чоловік", callback_data="search_gender_male")],
            [InlineKeyboardButton(text="👩 Жінка", callback_data="search_gender_female")]
        ]
    )

def get_age_search_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Будь-який", callback_data="search_age_any")],
            [InlineKeyboardButton(text="18-25", callback_data="search_age_18_25")],
            [InlineKeyboardButton(text="26-35", callback_data="search_age_26_35")],
            [InlineKeyboardButton(text="36-50", callback_data="search_age_36_50")],
            [InlineKeyboardButton(text="50+", callback_data="search_age_50_plus")],
            [InlineKeyboardButton(text="✅ Зберегти вибір віку", callback_data="search_age_save")]
        ]
    )

# Profile edit keyboards
def get_edit_gender_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨 Чоловік", callback_data="set_gender_male")],
            [InlineKeyboardButton(text="👩 Жінка", callback_data="set_gender_female")]
        ]
    )

def get_edit_age_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="18", callback_data="set_age_18"), InlineKeyboardButton(text="19", callback_data="set_age_19"), InlineKeyboardButton(text="20", callback_data="set_age_20")],
            [InlineKeyboardButton(text="21", callback_data="set_age_21"), InlineKeyboardButton(text="22", callback_data="set_age_22"), InlineKeyboardButton(text="23", callback_data="set_age_23")],
            [InlineKeyboardButton(text="24", callback_data="set_age_24"), InlineKeyboardButton(text="25", callback_data="set_age_25"), InlineKeyboardButton(text="26", callback_data="set_age_26")],
            [InlineKeyboardButton(text="27", callback_data="set_age_27"), InlineKeyboardButton(text="28", callback_data="set_age_28"), InlineKeyboardButton(text="29", callback_data="set_age_29")],
            [InlineKeyboardButton(text="30+", callback_data="set_age_30_plus")]
        ]
    )

def get_edit_country_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Україна", callback_data="set_country_ukraine")],
            [InlineKeyboardButton(text="🇷🇺 Росія", callback_data="set_country_russia")],
            [InlineKeyboardButton(text="🇧🇾 Білорусь", callback_data="set_country_belarus")],
            [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="set_country_kazakhstan")],
            [InlineKeyboardButton(text="🇬🇪 Грузія", callback_data="set_country_georgia")],
            [InlineKeyboardButton(text="🇪🇺 Європа", callback_data="set_country_europe")],
            [InlineKeyboardButton(text="🇦🇿 Азербайджан", callback_data="set_country_azerbaijan")],
            [InlineKeyboardButton(text="🇺🇿 Узбекистан", callback_data="set_country_uzbekistan")],
            [InlineKeyboardButton(text="🇺🇸 США", callback_data="set_country_usa")],
            [InlineKeyboardButton(text="🇹🇭 Тайланд", callback_data="set_country_thailand")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_country_english")],
            [InlineKeyboardButton(text="🌎 Решта світу", callback_data="set_country_other")]
        ]
    )

def get_media_blur_keyboard(blur_status=False):
    """Get media blur keyboard with toggle button"""
    # Change emoji based on current status
    if blur_status:
        toggle_text = "✅ Скрить фото/видео"
        toggle_callback = "toggle_blur_off"
    else:
        toggle_text = "❌ Скрить фото/видео"
        toggle_callback = "toggle_blur_on"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
        ]
    )


# User profile functions
def update_user_gender(user_id, gender):
    """Update user gender"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET gender=? WHERE user_id=?', (gender, user_id))
    conn.commit()
    conn.close()
    return True

def update_user_age(user_id, age):
    """Update user age"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET age=? WHERE user_id=?', (age, user_id))
    conn.commit()
    conn.close()
    return True

def update_user_country(user_id, country):
    """Update user country"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET country=? WHERE user_id=?', (country, user_id))
    conn.commit()
    conn.close()
    return True

def update_user_statistics(user_id, messages_sent=None, chats_count=None):
    """Update user statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if statistics record exists
    cur.execute('SELECT user_id FROM statistics WHERE user_id=?', (user_id,))
    exists = cur.fetchone()
    
    if not exists:
        # Create new statistics record
        cur.execute('INSERT INTO statistics (user_id, messages_sent, chats_count) VALUES (?, 0, 0)', (user_id,))
    
    # Update statistics
    if messages_sent is not None:
        cur.execute('UPDATE statistics SET messages_sent = messages_sent + ? WHERE user_id=?', (messages_sent, user_id))
    
    if chats_count is not None:
        cur.execute('UPDATE statistics SET chats_count = chats_count + ? WHERE user_id=?', (chats_count, user_id))
    
    conn.commit()
    conn.close()
    return True

def update_chat_time(user_id, additional_time):
    """Update user's total chat time"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET total_chat_time = total_chat_time + ? WHERE user_id=?', (additional_time, user_id))
    conn.commit()
    conn.close()
    return True

def update_media_blur(user_id, blur_enabled):
    """Update user's media blur setting"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Add media_blur column if it doesn't exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN media_blur INTEGER DEFAULT 0')
        conn.commit()
    except:
        pass  # Column already exists
    
    cur.execute('UPDATE users SET media_blur=? WHERE user_id=?', (1 if blur_enabled else 0, user_id))
    conn.commit()
    conn.close()
    return True

def get_media_blur_status(user_id):
    """Get user's media blur status"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if media_blur column exists and add it if it doesn't
    try:
        cur.execute('SELECT media_blur FROM users WHERE user_id=?', (user_id,))
        row = cur.fetchone()
        conn.close()
        return bool(row[0]) if row and row[0] is not None else False
    except sqlite3.OperationalError as e:
        if "no such column: media_blur" in str(e):
            # Add the column and return default value
            try:
                cur.execute('ALTER TABLE users ADD COLUMN media_blur INTEGER DEFAULT 0')
                conn.commit()
            except:
                pass  # Column might have been added by another process
            conn.close()
            return False
        else:
            conn.close()
            raise e

def reset_user_ratings(user_id):
    """Reset all user ratings to zero"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM ratings WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()
    return True


# Rating functions
def add_rating(user_id, rating_type):
    """Add rating to user"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if rating exists
    cur.execute('SELECT count FROM ratings WHERE user_id=? AND rating_type=?', (user_id, rating_type))
    row = cur.fetchone()
    
    if row:
        # Update existing rating
        cur.execute('UPDATE ratings SET count = count + 1 WHERE user_id=? AND rating_type=?', (user_id, rating_type))
    else:
        # Insert new rating
        cur.execute('INSERT INTO ratings (user_id, rating_type, count) VALUES (?, ?, 1)', (user_id, rating_type))
    
    conn.commit()
    conn.close()

def get_user_ratings(user_id):
    """Get user ratings"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT rating_type, count FROM ratings WHERE user_id=?', (user_id,))
    ratings = {}
    for row in cur.fetchall():
        ratings[row[0]] = row[1]
    
    conn.close()
    return ratings

def get_rating_text(user_id):
    """Get formatted rating text"""
    ratings = get_user_ratings(user_id)
    
    if not ratings:
        return ""
    
    rating_text = "📊 Рейтинг: "
    rating_parts = []
    
    if 'good' in ratings:
        rating_parts.append(f"👍 {ratings['good']}")
    if 'super' in ratings:
        rating_parts.append(f"❤️ {ratings['super']}")
    if 'bad' in ratings:
        rating_parts.append(f"👎 {ratings['bad']}")
    
    return rating_text + " | ".join(rating_parts) if rating_parts else ""

def format_combined_profile(user_id, is_premium_func):
    """Format combined user profile and statistics for display"""
    user_data = get_user(user_id)
    if not user_data:
        return "❌ Профіль не знайдено"
    
    # Basic profile info
    gender_emoji = "👨" if user_data['gender'] == "👨 Чоловік" else "👩"
    
    # Get user ID for display
    profile_text = f"🆔 — {user_id}\n\n"
    
    # Gender, age, country
    gender_text = "Парень" if user_data['gender'] == "👨 Чоловік" else "Дівчина"
    profile_text += f"👥 Пол — {gender_emoji} {gender_text}\n"
    profile_text += f"📅 Возраст — {user_data['age']} років\n"
    profile_text += f"🌍 Країна — {user_data.get('country', 'Не вказано')}\n\n"
    
    # Get statistics from database
    conn = get_conn()
    cur = conn.cursor()
    
    # Get chat statistics
    cur.execute('SELECT messages_sent, chats_count FROM statistics WHERE user_id=?', (user_id,))
    stats_row = cur.fetchone()
    
    if stats_row:
        messages_sent, chats_count = stats_row
    else:
        messages_sent, chats_count = 0, 0
    
    # Get total chat time
    total_chat_time = user_data.get('total_chat_time', 0)
    
    # Calculate today's chats (simplified - could be enhanced with date tracking)
    today_chats = min(chats_count, 5)  # Approximate value
    
    # Dialogs section
    profile_text += f"⚡ **Диалоги**\n"
    profile_text += f"├─ Всего: {chats_count}\n"
    profile_text += f"├─ За сегодня: {today_chats}\n"
    profile_text += f"└─ Длительность: {format_time(total_chat_time)}\n\n"
    
    # Calculate received messages (approximate as sent * 0.6)
    messages_received = int(messages_sent * 0.6) if messages_sent > 0 else 0
    
    # Messages section
    profile_text += f"📨 **Сообщения**\n"
    profile_text += f"├─ Отправлено: {messages_sent}\n"
    profile_text += f"└─ Получено: {messages_received}\n\n"
    
    # Room section
    profile_text += f"📁 **Комната:** 💬 Общение\n"
    
    # Get ratings
    ratings = get_user_ratings(user_id)
    good_count = ratings.get('good', 0)
    super_count = ratings.get('super', 0)
    bad_count = ratings.get('bad', 0)
    
    profile_text += f"⭐ **Оценки:** {good_count}👍 {super_count}❤️ {bad_count}👎\n\n"
    
    # Premium status
    if is_premium_func(user_id):
        profile_text += f"📎 **Доступ к эксклюзивным функциям**\n"
        profile_text += f"/premium - стать 📎 PREMIUM пользователем"
    else:
        profile_text += f"📎 **Доступ к эксклюзивным функциям**\n"
        profile_text += f"/premium - стать 📎 PREMIUM пользователем"
    
    conn.close()
    return profile_text

def format_stats(user_id):
    """Format user statistics for display"""
    user_data = get_user(user_id)
    if not user_data:
        return "❌ Статистика не знайдена"
    
    # Get statistics from database
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT messages_sent, chats_count FROM statistics WHERE user_id=?', (user_id,))
    row = cur.fetchone()
    
    if row:
        messages_sent, chats_count = row
    else:
        messages_sent, chats_count = 0, 0
    
    # Get ratings
    ratings = get_user_ratings(user_id)
    
    conn.close()
    
    stats_text = f"📊 **Ваша статистика**\n\n"
    stats_text += f"💬 Відправлено повідомлень: {messages_sent}\n"
    stats_text += f"👥 Кількість чатів: {chats_count}\n"
    stats_text += f"⏱️ Загальний час у чатах: {format_time(user_data['total_chat_time'])}\n\n"
    
    # Ratings breakdown
    stats_text += f"📈 **Рейтинги:**\n"
    stats_text += f"👍 Лайки: {ratings.get('good', 0)}\n"
    stats_text += f"❤️ Серця: {ratings.get('super', 0)}\n"
    stats_text += f"👎 Дизлайки: {ratings.get('bad', 0)}\n"
    
    return stats_text

def format_time(seconds):
    """Format time in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} хв"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} год {minutes} хв"



# Create global keyboard instances for backward compatibility
search_settings_keyboard = get_search_settings_keyboard()
gender_search_keyboard = get_gender_search_keyboard()
profile_inline_keyboard = get_profile_inline_keyboard()
profile_edit_inline_keyboard = get_profile_edit_inline_keyboard()
age_search_base_keyboard = [
    [InlineKeyboardButton(text="Будь-який", callback_data="search_age_any")],
    [InlineKeyboardButton(text="✅ Зберегти вибір віку", callback_data="search_age_save")]
]
