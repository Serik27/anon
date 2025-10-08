import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration from .env
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')

if not ADMIN_BOT_TOKEN or not ADMIN_USER_ID:
    raise ValueError("ADMIN_BOT_TOKEN and ADMIN_USER_ID must be set in .env file")

# Initialize bot and dispatcher
bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return str(user_id) == ADMIN_USER_ID

@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Handle /start command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цього бота.")
        return
    
    await message.answer(
        "🛡️ **Бот для обробки скарг - Версія 2.0**\n\n"
        "Цей бот допомагає модерувати користувачів з великою кількістю скарг.\n\n"
        "**Доступні команди:**\n"
        "• /start - запуск та перезапуск бота\n"
        "• /ban [id/username] - заблокувати користувача\n"
        "• /unban [id/username] - розблокувати користувача\n"
        "• /list_messages [id/username] - показати бесіди користувача (18-20 скарг)\n"
        "• /list_report [id/username] - показати список користувачів з 10+ скаргами\n"
        "• /help - детальна допомога\n\n"
        "Користувачі потрапляють на перевірку при 20+ скаргах."
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    """Handle /help command"""
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
🛡️ **Детальна допомога по боту обробки скарг**

**Команди:**

🚀 **/start**
Запуск та перезапуск бота. Показує основну інформацію та список команд.

🚫 **/ban [id/username]**
Блокує доступ користувача до анонімного чату назавжди.
Приклади:
• `/ban 123456789`
• `/ban @username`

✅ **/unban [id/username]**
Прибирає блокування користувача, дозволяє користуватися анонімним чатом.
Приклади:
• `/unban 123456789`
• `/unban @username`

📝 **/list_messages [id/username]**
Показує бесіди користувача, коли в нього було 18-20 скарг.
Відображаються повідомлення з того періоду, коли накопичувалися критичні скарги.
Приклади:
• `/list_messages 123456789`
• `/list_messages @username`

📊 **/list_report [id/username]**
Показує список користувачів з 10+ скаргами у вигляді inline кнопок.
При натисканні на кнопку з користувачем показуються його бесіди.
Приклад:
• `/list_report` - показати всіх
• `/list_report 123456789` - показати конкретного

❓ **/help**
Показує цю детальну допомогу.

**Логіка роботи:**
1. Користувачі скаржаться через основний бот
2. При 18 скаргах починається збереження бесід
3. При 20 скаргах користувач потрапляє на перевірку
4. Адмін може переглянути бесіди з 18-20 скарги
5. Адмін приймає рішення про блокування
"""
    
    await message.answer(help_text)

@dp.message(Command("ban"))
async def ban_command(message: types.Message):
    """Handle /ban command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "❌ **Неправильний формат команди**\n\n"
            "**Використання:**\n"
            "• `/ban 123456789` - заблокувати за ID\n"
            "• `/ban @username` - заблокувати за username"
        )
        return
    
    target = args[0]
    user_id = await resolve_user_id(target)
    
    if not user_id:
        await message.answer(f"❌ Не вдалося знайти користувача: {target}")
        return
    
    # Block user
    from complaints_system import block_user, get_user_info_for_complaint
    
    try:
        block_user(user_id, message.from_user.id, "Заблоковано адміністратором")
        
        user_info = get_user_info_for_complaint(user_id)
        user_name = user_info['first_name'] if user_info else 'Невідомо'
        
        await message.answer(
            f"🚫 **Користувача заблоковано**\n\n"
            f"👤 Користувач: {user_name}\n"
            f"🆔 ID: `{user_id}`\n"
            f"👮 Заблокував: {message.from_user.first_name}\n"
            f"📅 Час: {message.date.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"✅ Користувач більше не може користуватися анонімним чатом."
        )
        
        logger.info(f"User {user_id} banned by admin {message.from_user.id}")
        
    except Exception as e:
        await message.answer(f"❌ Помилка при блокуванні: {e}")

@dp.message(Command("unban"))
async def unban_command(message: types.Message):
    """Handle /unban command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "❌ **Неправильний формат команди**\n\n"
            "**Використання:**\n"
            "• `/unban 123456789` - розблокувати за ID\n"
            "• `/unban @username` - розблокувати за username"
        )
        return
    
    target = args[0]
    user_id = await resolve_user_id(target)
    
    if not user_id:
        await message.answer(f"❌ Не вдалося знайти користувача: {target}")
        return
    
    # Unblock user
    from complaints_system import unblock_user, get_user_info_for_complaint
    
    try:
        unblock_user(user_id)
        
        user_info = get_user_info_for_complaint(user_id)
        user_name = user_info['first_name'] if user_info else 'Невідомо'
        
        await message.answer(
            f"✅ **Користувача розблоковано**\n\n"
            f"👤 Користувач: {user_name}\n"
            f"🆔 ID: `{user_id}`\n"
            f"👮 Розблокував: {message.from_user.first_name}\n"
            f"📅 Час: {message.date.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"✅ Користувач може знову користуватися анонімним чатом."
        )
        
        logger.info(f"User {user_id} unblocked by admin {message.from_user.id}")
        
    except Exception as e:
        await message.answer(f"❌ Помилка при розблокуванні: {e}")

@dp.message(Command("list_messages"))
async def list_messages_command(message: types.Message):
    """Handle /list_messages command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "❌ **Неправильний формат команди**\n\n"
            "**Використання:**\n"
            "• `/list_messages 123456789` - показати бесіди за ID\n"
            "• `/list_messages @username` - показати бесіди за username"
        )
        return
    
    target = args[0]
    user_id = await resolve_user_id(target)
    
    if not user_id:
        await message.answer(f"❌ Не вдалося знайти користувача: {target}")
        return
    
    # Get user messages from critical period (18-20 complaints)
    from complaints_system import get_critical_period_messages, get_user_info_for_complaint
    
    try:
        messages = get_critical_period_messages(user_id)
        user_info = get_user_info_for_complaint(user_id)
        user_name = user_info['first_name'] if user_info else 'Невідомо'
        
        if not messages:
            await message.answer(
                f"📝 **Бесіди користувача**\n\n"
                f"👤 Користувач: {user_name} (ID: {user_id})\n"
                f"❌ Немає збережених бесід з критичного періоду (18-20 скарг)"
            )
            return
        
        # Format messages
        messages_text = f"📝 **Бесіди користувача з критичного періоду**\n\n"
        messages_text += f"👤 Користувач: {user_name} (ID: {user_id})\n"
        messages_text += f"📊 Знайдено повідомлень: {len(messages)}\n\n"
        
        for i, msg in enumerate(messages[:10], 1):  # Show first 10 messages
            message_text, media_type, timestamp, partner_id = msg
            
            import datetime
            dt = datetime.datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%d.%m.%Y %H:%M")
            
            messages_text += f"{i}. [{time_str}] "
            if message_text:
                messages_text += f"Текст: {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n"
            elif media_type:
                messages_text += f"Медіа: {media_type}\n"
            else:
                messages_text += "Порожнє повідомлення\n"
        
        if len(messages) > 10:
            messages_text += f"\n... та ще {len(messages) - 10} повідомлень"
        
        await message.answer(messages_text)
        
    except Exception as e:
        await message.answer(f"❌ Помилка при отриманні бесід: {e}")

@dp.message(Command("list_report"))
async def list_report_command(message: types.Message):
    """Handle /list_report command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return
    
    # Get users with 10+ complaints
    from complaints_system import get_users_with_complaints
    
    try:
        users = get_users_with_complaints(min_complaints=10)
        
        if not users:
            await message.answer(
                "📊 **Список користувачів зі скаргами**\n\n"
                "✅ Немає користувачів з 10+ скаргами"
            )
            return
        
        # Create inline keyboard with user buttons
        keyboard_buttons = []
        
        for user_id, complaint_count in users[:20]:  # Show max 20 users
            from complaints_system import get_user_info_for_complaint
            user_info = get_user_info_for_complaint(user_id)
            user_name = user_info['first_name'] if user_info else f"ID:{user_id}"
            
            button_text = f"{user_name} ({complaint_count} скарг)"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text, 
                    callback_data=f"show_user_{user_id}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        report_text = f"📊 **Список користувачів зі скаргами**\n\n"
        report_text += f"👥 Знайдено користувачів: {len(users)}\n"
        report_text += f"📋 Показано: {min(len(users), 20)}\n\n"
        report_text += "👆 Натисніть на користувача, щоб переглянути його бесіди:"
        
        await message.answer(report_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Помилка при отриманні списку: {e}")

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    """Handle callback queries"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу.")
        return
    
    if callback.data.startswith("show_user_"):
        user_id = int(callback.data.replace("show_user_", ""))
        await show_user_details(callback, user_id)

async def show_user_details(callback: types.CallbackQuery, user_id: int):
    """Show detailed user information and messages"""
    try:
        from complaints_system import (
            get_user_info_for_complaint, 
            get_complaint_count,
            get_critical_period_messages,
            is_user_blocked
        )
        
        user_info = get_user_info_for_complaint(user_id)
        complaint_count = get_complaint_count(user_id)
        messages = get_critical_period_messages(user_id)
        is_blocked = is_user_blocked(user_id)
        
        user_name = user_info['first_name'] if user_info else 'Невідомо'
        
        # Format user details
        details_text = f"👤 **Детальна інформація про користувача**\n\n"
        details_text += f"• Ім'я: {user_name}\n"
        details_text += f"• ID: `{user_id}`\n"
        details_text += f"• Username: @{user_info['username'] if user_info else 'немає'}\n"
        details_text += f"• Вік: {user_info['age'] if user_info else 'невідомо'}\n"
        details_text += f"• Стать: {user_info['gender'] if user_info else 'невідомо'}\n"
        details_text += f"• Країна: {user_info['country'] if user_info else 'невідомо'}\n"
        details_text += f"• Скарг: {complaint_count}\n"
        details_text += f"• Статус: {'🚫 Заблокований' if is_blocked else '✅ Активний'}\n\n"
        
        if messages:
            details_text += f"📝 **Останні повідомлення ({len(messages)}):**\n"
            for i, msg in enumerate(messages[:5], 1):
                message_text, media_type, timestamp, partner_id = msg
                
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%d.%m %H:%M")
                
                details_text += f"{i}. [{time_str}] "
                if message_text:
                    details_text += f"{message_text[:50]}{'...' if len(message_text) > 50 else ''}\n"
                elif media_type:
                    details_text += f"Медіа: {media_type}\n"
                else:
                    details_text += "Порожнє\n"
        else:
            details_text += "📝 Немає збережених повідомлень"
        
        # Create action buttons
        action_buttons = []
        if is_blocked:
            action_buttons.append([
                InlineKeyboardButton(text="✅ Розблокувати", callback_data=f"unban_{user_id}")
            ])
        else:
            action_buttons.append([
                InlineKeyboardButton(text="🚫 Заблокувати", callback_data=f"ban_{user_id}")
            ])
        
        action_buttons.append([
            InlineKeyboardButton(text="🔙 Назад до списку", callback_data="back_to_list")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=action_buttons)
        
        await callback.message.edit_text(details_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Помилка: {e}", show_alert=True)

async def resolve_user_id(target: str) -> int:
    """Resolve user ID from username or ID string"""
    try:
        # If it's a number, return as int
        if target.isdigit():
            return int(target)
        
        # If it starts with @, remove it and search by username
        if target.startswith('@'):
            username = target[1:]
            from registration_aiogram import get_conn
            
            conn = get_conn()
            cur = conn.cursor()
            cur.execute('SELECT user_id FROM users WHERE username = ?', (username,))
            row = cur.fetchone()
            conn.close()
            
            return row[0] if row else None
        
        return None
    except:
        return None

async def main():
    """Main function to run the bot"""
    logger.info("Starting admin complaints bot v2.0...")
    
    try:
        # Start polling
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
