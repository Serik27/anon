import time
from aiogram import types
from aiogram.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton

# Import from registration module
from registration_aiogram import get_conn

# Вартість і тривалість підписок (у секундах)
PREMIUM_PRICES = {
    '1day': {'stars': 49, 'duration': 1 * 24 * 3600},
    '7days': {'stars': 200, 'duration': 7 * 24 * 3600},
    '30days': {'stars': 399, 'duration': 30 * 24 * 3600},
    '365days': {'stars': 999, 'duration': 365 * 24 * 3600},
    'forever': {'stars': 350, 'duration': 50 * 365 * 24 * 3600},  # 50 років = "навіки"
}

# PRO статус ціна
PRO_PRICE = {
    'pro_month': {'stars': 3499, 'duration': 30 * 24 * 3600}  # 30 днів
}

# Валюта для Stars
CURRENCY = "XTR"

# Premium benefits text
PREMIUM_BENEFITS_TEXT = """
💎 Спілкуйся з PREMIUM без обмежень!

🌟 Переваги:
• приоритет при пошуку
• пришвидчена робота бота
• пошук по статі та віку
• повне відключення реклами
• відправлення любих стикер-паків
• доступні кімнати для інтересів
• не потрібно підписуватися на канали
• доступна кнопка повернути співрозмовника
• знак 💎 PREMIUM буде видно співрозмовнику
• відкрита інформація про співрозмовника (стать та вік)

Здійснюючи покупку Ви підтверджуєте, що ознайомилися і згідні з Користувацькою згодою.
"""

# PRO benefits text
PRO_BENEFITS_TEXT = """
🌟 ПОЛУЧИТЬ ВОЗМОЖНОСТИ АДМИНИСТРАТОРА

🚀 PRO статус включає:
• ВСІ переваги PREMIUM статусу
• Система друзів - додавання та управління
• Запити на розмову до друзів
• Статистика активності друзів
• Анонімний режим спілкування
• Розширена статистика користувачів
• Пріоритетна підтримка
• Знак 🌟 PRO буде видно співрозмовнику
• Доступ до PRO команд та функцій

💰 Ціна: 3499⭐ (на місяць)

Здійснюючи покупку Ви підтверджуєте, що ознайомилися і згідні з Користувацькою згодою.
"""

def get_premium_keyboard():
    """Get premium purchase keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌟 PRO-статус", callback_data="show_pro_purchase")],
            [InlineKeyboardButton(text="⚡ 1 день - 49⭐", callback_data="buy_1day")],
            [InlineKeyboardButton(text="🔥 7 днів - 200⭐", callback_data="buy_7days")],
            [InlineKeyboardButton(text="📅 Місяць - 399⭐", callback_data="buy_30days")],
            [InlineKeyboardButton(text="🎯 Рік - 999⭐", callback_data="buy_365days")],
            [InlineKeyboardButton(text="🎁 Отримати безкоштовно", callback_data="free_premium")]
        ]
    )

def get_pro_keyboard():
    """Get PRO purchase keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌟 Купити PRO - 3499⭐", callback_data="buy_pro_month")],
            [InlineKeyboardButton(text="🔙 Назад до Premium", callback_data="back_to_premium")]
        ]
    )

async def premium_menu(message: types.Message):
    """Show premium menu"""
    await message.answer(
        PREMIUM_BENEFITS_TEXT + "\n\n🌟 ПОЛУЧИТЬ ВОЗМОЖНОСТИ АДМИНИСТРАТОРА\n\nВиберіть преміум-підписку:",
        reply_markup=get_premium_keyboard()
    )

async def show_pro_purchase(callback: types.CallbackQuery):
    """Show PRO purchase menu"""
    await callback.message.edit_text(
        PRO_BENEFITS_TEXT,
        reply_markup=get_pro_keyboard()
    )

async def back_to_premium(callback: types.CallbackQuery):
    """Go back to premium menu"""
    await callback.message.edit_text(
        PREMIUM_BENEFITS_TEXT + "\n\n🌟 ПОЛУЧИТЬ ВОЗМОЖНОСТИ АДМИНИСТРАТОРА\n\nВиберіть преміум-підписку:",
        reply_markup=get_premium_keyboard()
    )

async def start_premium_purchase(callback: types.CallbackQuery):
    """Start premium purchase process"""
    user_id = callback.from_user.id
    option = callback.data.replace('buy_', '')
    
    print(f"start_premium_purchase викликано з опцією: {option}")
    
    # Check if it's PRO purchase
    if option == 'pro_month':
        price_info = PRO_PRICE.get(option)
        title = "Покупка PRO статусу"
    else:
        price_info = PREMIUM_PRICES.get(option)
        title = "Покупка PREMIUM"
    
    if not price_info:
        await callback.answer("Невірна підписка")
        return

    amount = price_info['stars']  # aiogram 3.x використовує Stars напряму
    
    if option == 'pro_month':
        description = "PRO статус на місяць"
    elif option == 'forever':
        description = "Преміум назавжди"
    elif option == '1day':
        description = "Преміум на 1 день"
    elif option == '7days':
        description = "Преміум на 7 днів"
    elif option == '30days':
        description = "Преміум на місяць"
    elif option == '365days':
        description = "Преміум на рік"
    else:
        description = f"Преміум підписка"
    
    payload = f"premium_{option}"
    
    print(f"Відправляємо інвойс користувачу {user_id}: {title}, {description}, {amount}")

    try:
        from bot_aiogram import bot
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            currency=CURRENCY,
            prices=[LabeledPrice(label=title, amount=amount)],
            start_parameter=f"premium_{option}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        await callback.answer()
    except Exception as e:
        print(f"Помилка при відправленні інвойсу: {e}")
        await callback.answer("Помилка при створенні платежу. Спробуйте пізніше.")

async def precheckout_callback(pre_checkout_query: types.PreCheckoutQuery):
    """Handle pre-checkout query"""
    await pre_checkout_query.answer(ok=True)

def add_pro_time(user_id, seconds):
    """Add PRO time to user"""
    current_time = int(time.time())
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Отримуємо поточний статус PRO
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    
    if row and row[0] > current_time:
        # Користувач вже має PRO - продовжуємо
        new_until = row[0] + seconds
    else:
        # Новий PRO або закінчився
        new_until = current_time + seconds
    
    # Оновлюємо базу даних
    cur.execute('UPDATE users SET pro_until = ? WHERE user_id = ?', (new_until, user_id))
    conn.commit()
    conn.close()
    
    return new_until

async def successful_payment_callback(message: types.Message):
    """Handle successful payment"""
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    print(f"Успішний платіж від користувача {user_id}: {payload}")
    
    # Розбираємо payload
    if payload.startswith('premium_'):
        option = payload.replace('premium_', '')
        
        # Check if it's PRO purchase
        if option == 'pro_month':
            price_info = PRO_PRICE.get(option)
            if price_info:
                # Додаємо PRO час
                duration = price_info['duration']
                add_pro_time(user_id, duration)
                await message.answer("🎉 Вітаємо! Ви отримали PRO статус на місяць! 🌟")
            else:
                await message.answer("❌ Помилка при обробці PRO платежу. Зверніться до підтримки.")
        else:
            price_info = PREMIUM_PRICES.get(option)
            if price_info:
                # Додаємо преміум час
                duration = price_info['duration']
                add_premium_time(user_id, duration)
                
                # Повідомляємо користувача
                if option == 'forever':
                    await message.answer("🎉 Вітаємо! Ви отримали преміум назавжди! 💎")
                elif option == '1day':
                    await message.answer("🎉 Вітаємо! Ви отримали преміум на 1 день! 💎")
                elif option == '7days':
                    await message.answer("🎉 Вітаємо! Ви отримали преміум на 7 днів! 💎")
                elif option == '30days':
                    await message.answer("🎉 Вітаємо! Ви отримали преміум на місяць! 💎")
                elif option == '365days':
                    await message.answer("🎉 Вітаємо! Ви отримали преміум на рік! 💎")
                else:
                    await message.answer("🎉 Вітаємо! Ви отримали преміум! 💎")
            else:
                await message.answer("❌ Помилка при обробці платежу. Зверніться до підтримки.")
    else:
        await message.answer("❌ Невідомий тип платежу.")

def is_pro(user_id):
    """Check if user has PRO status"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row and row[0]:
        return int(time.time()) < row[0]
    return False

def get_pro_required_keyboard():
    """Get keyboard for PRO required message"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌟 PRO-статус", callback_data="show_pro_purchase")]
        ]
    )

async def send_pro_required_message(message_or_callback, command_name="команда"):
    """Send message that PRO is required"""
    text = f"🌟 **PRO статус потрібен**\n\n" \
           f"Ця {command_name} доступна тільки PRO користувачам.\n\n" \
           f"PRO статус включає:\n" \
           f"• ВСІ переваги PREMIUM статусу\n" \
           f"• Система друзів та управління\n" \
           f"• Розширена статистика\n" \
           f"• Анонімний режим\n" \
           f"• Пріоритетна підтримка\n\n" \
           f"💰 Ціна: 3499⭐ (на місяць)"
    
    keyboard = get_pro_required_keyboard()
    
    if hasattr(message_or_callback, 'message'):
        # It's a callback
        await message_or_callback.message.answer(text, reply_markup=keyboard)
    else:
        # It's a message
        await message_or_callback.answer(text, reply_markup=keyboard)

def is_premium(user_id):
    """Check if user has premium status (PRO users also have premium privileges)"""
    # PRO users have all premium privileges
    if is_pro(user_id):
        return True
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row and row[0]:
        return int(time.time()) < row[0]
    return False

def get_user_status(user_id):
    """Get user status: 'pro', 'premium', or 'regular'"""
    # Check PRO status first (without calling is_premium to avoid recursion)
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT pro_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    
    if row and row[0] and int(time.time()) < row[0]:
        conn.close()
        return 'pro'
    
    # Check premium status
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row and row[0] and int(time.time()) < row[0]:
        return 'premium'
    else:
        return 'regular'

def get_premium_until(user_id):
    """Get premium expiration timestamp"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    
    return row[0] if row and row[0] else 0

def add_premium_time(user_id, seconds):
    """Add premium time to user"""
    current_time = int(time.time())
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Отримуємо поточний статус преміум
    cur.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    
    if row and row[0] > current_time:
        # Користувач вже має преміум - продовжуємо
        new_until = row[0] + seconds
    else:
        # Новий преміум або закінчився
        new_until = current_time + seconds
    
    # Оновлюємо базу даних
    cur.execute('UPDATE users SET premium_until = ? WHERE user_id = ?', (new_until, user_id))
    conn.commit()
    conn.close()
    
    return new_until

def remove_premium(user_id):
    """Remove premium status from user"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('UPDATE users SET premium_until = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_premium_stats():
    """Get premium statistics"""
    conn = get_conn()
    cur = conn.cursor()
    
    current_time = int(time.time())
    
    # Активні преміум користувачі
    cur.execute('SELECT COUNT(*) FROM users WHERE premium_until > ?', (current_time,))
    active_premium = cur.fetchone()[0]
    
    # Всього користувачів з преміумом (включаючи тих, у кого закінчився)
    cur.execute('SELECT COUNT(*) FROM users WHERE premium_until > 0')
    total_premium = cur.fetchone()[0]
    
    # Всього користувачів
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    
    conn.close()
    
    return {
        'active_premium': active_premium,
        'total_premium': total_premium,
        'total_users': total_users,
        'premium_percentage': (active_premium / total_users * 100) if total_users > 0 else 0
    }

def get_referral_count(user_id):
    """Get referral count for user"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Create referrals table if not exists
    cur.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s', 'now'))
    )
    ''')
    
    cur.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    count = cur.fetchone()[0]
    conn.close()
    
    return count

def get_available_reward(referral_count, user_id=None):
    """Get available reward based on referral count"""
    rewards = [
        (50, 4 * 24 * 3600, "4 дні"),  # 50 друзів - 4 дні
        (20, 24 * 3600, "1 день"),     # 20 друзів - 1 день
        (10, 8 * 3600, "8 годин"),     # 10 друзів - 8 годин
        (5, 3 * 3600, "3 години")      # 5 друзів - 3 години
    ]
    
    # Get used rewards if user_id provided
    used_rewards = []
    if user_id:
        used_rewards = get_used_referral_rewards(user_id)
    
    print(f"DEBUG get_available_reward: referral_count={referral_count}, used_rewards={used_rewards}")
    
    for required_count, duration, description in rewards:
        print(f"DEBUG checking: required_count={required_count}, referral_count >= required_count: {referral_count >= required_count}, not in used_rewards: {required_count not in used_rewards}")
        if referral_count >= required_count and required_count not in used_rewards:
            print(f"DEBUG found reward: {required_count}, {duration}, {description}")
            return required_count, duration, description
    
    print("DEBUG: No reward found")
    return None, None, None

def get_next_reward_info(referral_count):
    """Get info about next reward"""
    rewards = [
        (5, "3 години"),
        (10, "8 годин"),
        (20, "1 день"),
        (50, "4 дні")
    ]
    
    for required_count, description in rewards:
        if referral_count < required_count:
            return required_count, description, required_count - referral_count
    
    return None, None, 0

async def show_referral_menu(callback: types.CallbackQuery):
    """Show referral menu for free premium"""
    user_id = callback.from_user.id
    
    # Get referral count
    referral_count = get_referral_count(user_id)
    
    # Create unique referral link
    from bot_aiogram import bot
    bot_info = await bot.get_me()
    username = bot_info.username
    referral_link = f"https://t.me/{username}?start=ref_{user_id}"
    
    # Get available reward
    reward_count, reward_duration, reward_description = get_available_reward(referral_count, user_id)
    
    # Debug info
    print(f"DEBUG: user_id={user_id}, referral_count={referral_count}")
    print(f"DEBUG: reward_count={reward_count}, reward_duration={reward_duration}, reward_description={reward_description}")
    
    # Get next reward info
    next_reward_count, next_reward_description, referrals_needed = get_next_reward_info(referral_count)
    
    # Create referral keyboard
    keyboard_buttons = [
        [InlineKeyboardButton(
            text="📤 Поділитися посиланням", 
            switch_inline_query=f"Приєднуйся до анонімного чату! {referral_link}"
        )]
    ]
    
    # Always show activate button - logic will be handled in the activation function
    keyboard_buttons.append([
        InlineKeyboardButton(text="🎁 Активувати нагороду", callback_data="activate_referral_reward")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад до преміум", callback_data="premium_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Format referral text
    referral_text = (
        f"🎁 **Отримай PREMIUM безкоштовно!**\n\n"
        f"📊 **Твоя статистика:**\n"
        f"👥 Запрошено друзів: **{referral_count}**\n"
    )
    
    if reward_count and reward_duration:
        referral_text += f"🎉 **Доступна нагорода:** {reward_description} преміуму!\n"
        referral_text += f"💡 Натисніть кнопку 'Активувати нагороду' щоб отримати преміум!\n"
    elif next_reward_count:
        referral_text += f"🎯 До наступної нагороди: **{referrals_needed}** друзів\n"
        referral_text += f"💡 Натисніть кнопку 'Активувати нагороду' щоб дізнатися деталі!\n"
    else:
        referral_text += f"💡 Натисніть кнопку 'Активувати нагороду' щоб дізнатися що потрібно!\n"
    
    referral_text += (
        f"\n🏆 **Система нагород:**\n"
        f"• За 5 рефералів - 3 години преміуму\n"
        f"• За 10 рефералів - 8 годин преміуму\n"
        f"• За 20 рефералів - 1 день преміуму\n"
        f"• За 50 рефералів - 4 дні преміуму\n\n"
        f"🔗 **Твоє реферальне посилання:**\n`{referral_link}`\n\n"
        f"Поділись цим посиланням з друзями. Коли вони зареєструються через твоє посилання, ти отримаєш бонуси!"
    )
    
    await callback.message.edit_text(
        referral_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

def init_referral_rewards_table():
    """Initialize referral rewards table"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS referral_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        reward_level INTEGER NOT NULL,
        activated_at INTEGER DEFAULT (strftime('%s', 'now')),
        UNIQUE(user_id, reward_level)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_used_referral_rewards(user_id):
    """Get list of used referral rewards for user"""
    # Ensure table exists
    init_referral_rewards_table()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('SELECT reward_level FROM referral_rewards WHERE user_id = ?', (user_id,))
    used_rewards = [row[0] for row in cur.fetchall()]
    conn.close()
    
    return used_rewards

def mark_referral_reward_used(user_id, reward_level):
    """Mark referral reward as used"""
    # Ensure table exists
    init_referral_rewards_table()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
    INSERT OR IGNORE INTO referral_rewards (user_id, reward_level)
    VALUES (?, ?)
    ''', (user_id, reward_level))
    
    conn.commit()
    conn.close()

async def activate_referral_reward(callback: types.CallbackQuery):
    """Activate referral reward for user"""
    user_id = callback.from_user.id
    
    # Get referral count
    referral_count = get_referral_count(user_id)
    
    # Get available reward
    reward_count, reward_duration, reward_description = get_available_reward(referral_count, user_id)
    
    # Check if no reward available
    if not reward_count or not reward_duration:
        # Determine what user needs
        if referral_count < 5:
            needed = 5 - referral_count
            await callback.answer(
                f"❌ Недостатньо рефералів!\n\n"
                f"У вас: {referral_count} рефералів\n"
                f"Потрібно ще: {needed} рефералів\n"
                f"Для отримання: 3 години преміуму",
                show_alert=True
            )
        elif referral_count < 10:
            # Check if 5-referral reward was already used
            used_rewards = get_used_referral_rewards(user_id)
            if 5 in used_rewards:
                needed = 10 - referral_count
                await callback.answer(
                    f"❌ Недостатньо рефералів!\n\n"
                    f"У вас: {referral_count} рефералів\n"
                    f"Потрібно ще: {needed} рефералів\n"
                    f"Для отримання: 8 годин преміуму",
                    show_alert=True
                )
            else:
                await callback.answer("❌ Помилка визначення нагороди!", show_alert=True)
        elif referral_count < 20:
            used_rewards = get_used_referral_rewards(user_id)
            if 10 in used_rewards:
                needed = 20 - referral_count
                await callback.answer(
                    f"❌ Недостатньо рефералів!\n\n"
                    f"У вас: {referral_count} рефералів\n"
                    f"Потрібно ще: {needed} рефералів\n"
                    f"Для отримання: 1 день преміуму",
                    show_alert=True
                )
            else:
                await callback.answer("❌ Помилка визначення нагороди!", show_alert=True)
        elif referral_count < 50:
            used_rewards = get_used_referral_rewards(user_id)
            if 20 in used_rewards:
                needed = 50 - referral_count
                await callback.answer(
                    f"❌ Недостатньо рефералів!\n\n"
                    f"У вас: {referral_count} рефералів\n"
                    f"Потрібно ще: {needed} рефералів\n"
                    f"Для отримання: 4 дні преміуму",
                    show_alert=True
                )
            else:
                await callback.answer("❌ Помилка визначення нагороди!", show_alert=True)
        else:
            await callback.answer("❌ Всі нагороди вже активовані!", show_alert=True)
        return
    
    # Add premium time
    add_premium_time(user_id, reward_duration)
    
    # Mark reward as used
    mark_referral_reward_used(user_id, reward_count)
    
    # Success message
    await callback.answer(
        f"🎉 Нагорода активована!\n\n"
        f"Отримано: {reward_description} преміуму",
        show_alert=True
    )
    
    # Update the menu
    await show_referral_menu(callback)

# Temporary function for testing - add fake referrals
def add_test_referrals(user_id, count):
    """Add test referrals for debugging (REMOVE IN PRODUCTION)"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Create referrals table if not exists
    cur.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s', 'now'))
    )
    ''')
    
    # Add fake referrals
    for i in range(count):
        fake_user_id = 999999 + i  # Use fake user IDs
        cur.execute('''
        INSERT OR IGNORE INTO referrals (referrer_id, referred_id)
        VALUES (?, ?)
        ''', (user_id, fake_user_id))
    
    conn.commit()
    conn.close()
