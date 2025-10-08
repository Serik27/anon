from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

# Import modules
from registration_aiogram import get_user
from user_profile_aiogram import (
    add_rating, get_rating_text, update_user_gender, 
    update_user_age, update_user_country,
    format_combined_profile, get_edit_gender_keyboard,
    get_edit_age_keyboard, get_edit_country_keyboard,
    get_media_blur_keyboard, update_media_blur,
    get_media_blur_status, reset_user_ratings
)
from premium_aiogram import is_premium, show_referral_menu, start_premium_purchase, get_premium_keyboard, activate_referral_reward
from chat_aiogram import get_partner, remove_active, add_waiting, search_by_user_id

# Global variables for state management
edit_profile_state = {}
user_interests = {}
user_section = {}
search_preferences = {}

async def handle_rating_callback(callback: types.CallbackQuery):
    """Handle rating callbacks"""
    _, rating_type, rated_user_id = callback.data.split('_')
    rated_user_id = int(rated_user_id)
    
    add_rating(rated_user_id, rating_type)
    await callback.answer(f"Ви оцінили співрозмовника! Дякуємо за відгук.")
    
    # Update message to remove rating buttons
    current_text = callback.message.text
    
    keyboard = [
        [InlineKeyboardButton(text="🚫 Поскаржитися", callback_data=f"report_{rated_user_id}")],
        [InlineKeyboardButton(text="🔄 Повернутися", callback_data=f"return_{rated_user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"{current_text}\n\n✅ Дякуємо за оцінку співрозмовника!",
        reply_markup=reply_markup
    )

async def handle_next_callback(callback: types.CallbackQuery):
    """Handle next partner callback"""
    user_id = callback.from_user.id
    await callback.answer("Шукаємо нового співрозмовника...")
    
    # Check if user is in chat first
    partner_id = get_partner(user_id)
    if partner_id:
        # End current chat
        from chat_aiogram import stop_chat_between_users
        await stop_chat_between_users(user_id, partner_id, callback.message)
    
    # Add user to waiting queue
    add_waiting(user_id)
    
    # Send searching message
    await callback.message.answer("Шукаємо нового співрозмовника...")
    
    # Try to find a partner
    await search_by_user_id(user_id, callback.message)



async def handle_premium_callback(callback: types.CallbackQuery):
    """Handle premium-related callbacks"""
    user_id = callback.from_user.id
    
    if callback.data == "get_premium":
        await callback.answer()
        from premium_aiogram import premium_menu
        await premium_menu(callback.message)
        
    elif callback.data == "free_premium":
        await callback.answer()
        await show_referral_menu(callback)
        
    elif callback.data == "activate_referral_reward":
        await activate_referral_reward(callback)
        
    elif callback.data.startswith("buy_"):
        await start_premium_purchase(callback)
        
    elif callback.data == "premium_menu":
        await callback.answer()
        from premium_aiogram import PREMIUM_BENEFITS_TEXT
        await callback.message.edit_text(
            PREMIUM_BENEFITS_TEXT + "\n\nВиберіть преміум-підписку:",
            reply_markup=get_premium_keyboard()
        )

async def handle_profile_callback(callback: types.CallbackQuery, state: FSMContext = None):
    """Handle profile-related callbacks"""
    user_id = callback.from_user.id
    
    if callback.data == "profile_view":
        profile_text = format_combined_profile(user_id, is_premium)
        from user_profile_aiogram import get_profile_edit_inline_keyboard
        await callback.message.edit_text(profile_text, reply_markup=get_profile_edit_inline_keyboard())
        user_section[user_id] = "profile_edit"
        
    elif callback.data == "profile_back":
        await callback.message.delete()
        await callback.message.answer("Головне меню:")
        if user_id in user_section:
            del user_section[user_id]
            
    # New profile edit handlers
    elif callback.data == "edit_gender":
        await callback.message.edit_text(
            "Выберите ваш пол:",
            reply_markup=get_edit_gender_keyboard()
        )
        
    elif callback.data == "edit_age":
        from bot_aiogram import ProfileEditStates
        
        if state:
            await state.set_state(ProfileEditStates.waiting_for_age_input)
        
        await callback.message.edit_text(
            "Введіть ваш вік (від 8 до 99 років):"
        )
        
    elif callback.data == "edit_country":
        await callback.message.edit_text(
            "Выберите вашу страну:",
            reply_markup=get_edit_country_keyboard()
        )
        
    elif callback.data == "toggle_media_blur":
        blur_status = get_media_blur_status(user_id)
        status_text = "включен" if blur_status else "виключен"
        
        info_text = (
            "🙈 **Скрить фото/видео**\n\n"
            "📷 Ця функція дозволяє скрити всі фото та відео, які ви отримуєте від співрозмовників.\n\n"
            "✅ **Включено**: всі медіа будуть заблюровані\n"
            "❌ **Вимкнено**: медіа будуть показані без блюру\n\n"
            f"🔄 **Поточний статус**: {status_text}"
        )
        
        await callback.message.edit_text(
            info_text,
            reply_markup=get_media_blur_keyboard(blur_status)
        )
        
    elif callback.data == "reset_ratings_stars":
        # Create Telegram Stars payment
        from aiogram.types import LabeledPrice
        await callback.message.answer_invoice(
            title="Обнулить оценки",
            description="Сбросить все ваши оценки до нуля",
            payload="reset_ratings",
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",  # Telegram Stars currency
            prices=[LabeledPrice(label="Обнулить оценки", amount=55)],
            start_parameter="reset_ratings"
        )
        
    elif callback.data == "invite_friend":
        await show_referral_menu(callback)
        
    elif callback.data == "back_to_profile":
        profile_text = format_combined_profile(user_id, is_premium)
        from user_profile_aiogram import get_profile_edit_inline_keyboard
        await callback.message.edit_text(profile_text, reply_markup=get_profile_edit_inline_keyboard())

async def handle_search_settings_callback(callback: types.CallbackQuery):
    """Handle search settings callbacks"""
    user_id = callback.from_user.id
    
    # Check premium requirements for search settings
    if callback.data.startswith(("search_setting_gender", "search_setting_age")):
        if not is_premium(user_id):
            await callback.answer("Ця функція доступна тільки для преміум користувачів!")
            from premium_aiogram import get_premium_keyboard
            await callback.message.answer(
                "⚠️ Ця функція доступна тільки для преміум користувачів!\n\n"
                "Отримайте преміум, щоб налаштувати пошук за статтю та віком.",
                reply_markup=get_premium_keyboard()
            )
            return
    
    if callback.data == "search_setting_gender":
        from user_profile_aiogram import get_gender_search_keyboard
        await callback.message.edit_text(
            "Оберіть стать для пошуку:",
            reply_markup=get_gender_search_keyboard()
        )
        
    elif callback.data == "search_setting_age":
        from user_profile_aiogram import get_age_search_keyboard
        await callback.message.edit_text(
            "Оберіть вікову групу для пошуку:",
            reply_markup=get_age_search_keyboard()
        )
        

async def handle_report_callback(callback: types.CallbackQuery):
    """Handle report callbacks"""
    _, reported_user_id = callback.data.split('_')
    reported_user_id = int(reported_user_id)
    reporter_id = callback.from_user.id
    
    # Check if user already complained about this user recently
    from complaints_system import add_complaint, has_user_complained_recently
    
    if has_user_complained_recently(reporter_id, reported_user_id):
        await callback.answer("Ви вже поскаржилися на цього користувача в цій сесії.", show_alert=True)
        return
    
    complaint_count = add_complaint(reporter_id, reported_user_id)
    
    await callback.answer("Скаргу надіслано. Дякуємо за допомогу в покращенні сервісу!")
    
    # Keep rating buttons but remove complaint button
    current_text = callback.message.text
    
    # Recreate rating buttons without complaint button
    keyboard = [
        [
            InlineKeyboardButton(text="👍 Добре", callback_data=f"rate_good_{reported_user_id}"),
            InlineKeyboardButton(text="👎 Погано", callback_data=f"rate_bad_{reported_user_id}"),
            InlineKeyboardButton(text="❤️ Супер", callback_data=f"rate_super_{reported_user_id}")
        ],
        [InlineKeyboardButton(text="🔄 Повернутися", callback_data=f"return_{reported_user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"{current_text}\n\n📋 Скаргу надіслано адміністрації.",
        reply_markup=reply_markup
    )
    
    # Note: Admin bot now works independently through admin_complaints_bot.py
    # No automatic notifications needed - admin uses /list_report command

async def handle_room_callback(callback: types.CallbackQuery):
    """Handle room selection callbacks"""
    user_id = callback.from_user.id
    
    room_map = {
        "room_general": "💬 Общение",
        "room_exchange": "🔞 Обмен 18+", 
        "room_lgbt": "🏳️‍🌈 ЛГБТ",
        "room_school": "🎓 Школа"
    }
    
    room_name = room_map.get(callback.data)
    if room_name:
        # Check if user is currently in chat or searching
        from chat_aiogram import get_partner, is_waiting
        partner_id = get_partner(user_id)
        if partner_id or is_waiting(user_id):
            await callback.answer(
                "❌ Неможливо змінити кімнату під час активного чату або пошуку співрозмовника. Завершіть розмову або пошук спочатку.",
                show_alert=True
            )
            return
        
        # Check if room is open
        from rooms_system import is_room_open, set_user_room, get_room_info
        
        if not is_room_open(callback.data):
            await callback.answer(
                f"❌ Кімната '{room_name}' тимчасово закрита адміністрацією.",
                show_alert=True
            )
            return
        
        # Check access to "Школа" room
        if callback.data == "room_school":
            from registration_aiogram import get_user
            from premium_aiogram import is_premium, is_pro
            
            user_data = get_user(user_id)
            if user_data:
                user_age = user_data.get('age', 0)
                
                # Check if user is 18+ and doesn't have premium/pro status
                if user_age >= 18 and not (is_premium(user_id) or is_pro(user_id)):
                    await callback.answer(
                        "❌ Доступ до кімнати 'Школа' заборонено для користувачів 18+ років.\n\n"
                        "Отримайте Premium або PRO статус для доступу до всіх кімнат!",
                        show_alert=True
                    )
                    return
        
        # Save user's room preference to database
        set_user_room(user_id, callback.data)
        
        # Show confirmation
        await callback.answer(f"Обрано кімнату: {room_name}")
        
        if callback.data == "room_school":
            await callback.message.edit_text(
                f'✅ Ви вибрали кімнату "Школа". Ця кімната строго контролюється адміністрацією, забезпечуючи безпеку для користувачів яким немає 18 років.\n\n'
                f"Тепер ви будете шукати співрозмовників у цій кімнаті."
            )
        else:
            await callback.message.edit_text(
                f"✅ Ви обрали кімнату: *{room_name}*\n\n"
                "Тепер ви будете шукати співрозмовників у цій кімнаті."
            )

async def handle_premium_search_callback(callback: types.CallbackQuery, state: FSMContext = None):
    """Handle premium search callbacks"""
    user_id = callback.from_user.id
    
    if callback.data == "premium_search_gender":
        from user_profile_aiogram import get_premium_gender_keyboard
        await callback.message.edit_text(
            "👤 **Выберите пол собеседника:**",
            reply_markup=get_premium_gender_keyboard()
        )
        
    elif callback.data == "premium_search_age":
        from user_profile_aiogram import get_premium_age_keyboard
        await callback.message.edit_text(
            "🔢 **Выберите возраст собеседника:**",
            reply_markup=get_premium_age_keyboard()
        )
        
    elif callback.data == "premium_search_country":
        from user_profile_aiogram import get_premium_country_keyboard
        await callback.message.edit_text(
            "🌍 **Выберите страны собеседника:**\n\n"
            "Можете выбрать несколько стран. Выбранные страны отмечены ✅",
            reply_markup=get_premium_country_keyboard(user_id)
        )
        
    elif callback.data == "premium_show_status":
        from user_profile_aiogram import get_premium_show_status_keyboard
        await callback.message.edit_text(
            "💎 **Показывать Premium статус:**\n\n"
            "Если включено, собеседники будут видеть что вы Premium пользователь.",
            reply_markup=get_premium_show_status_keyboard(user_id)
        )
        
    elif callback.data == "premium_user_type":
        from user_profile_aiogram import get_premium_user_type_keyboard
        await callback.message.edit_text(
            "🔍 **Тип пользователей для поиска:**",
            reply_markup=get_premium_user_type_keyboard()
        )
        
    elif callback.data == "premium_search_back":
        from user_profile_aiogram import get_search_settings_keyboard, get_search_preferences_text
        await callback.message.edit_text(
            get_search_preferences_text(user_id),
            reply_markup=get_search_settings_keyboard(user_id)
        )
        
    elif callback.data == "premium_start_search":
        await callback.answer("Запускаємо преміум пошук...")
        user_id = callback.from_user.id
        
        # Check if already in chat or searching
        from chat_aiogram import get_partner, is_waiting, start_premium_search
        if get_partner(user_id):
            await callback.message.edit_text("Ви вже у чаті! Завершіть поточний чат перед пошуком нового співрозмовника.")
            return
        if is_waiting(user_id):
            await callback.message.edit_text("Ви вже шукаєте співрозмовника!")
            return
            
        # Start premium search
        await start_premium_search(callback.message)
        
    # Handle specific selections
    elif callback.data.startswith("premium_gender_"):
        gender = callback.data.replace("premium_gender_", "")
        gender_text = {"any": "Любой", "male": "Парни", "female": "Девушки"}.get(gender, "Любой")
        
        # Save preference
        from user_profile_aiogram import set_search_preference, get_search_settings_keyboard
        set_search_preference(user_id, 'gender', gender)
        
        await callback.answer(f"Выбран пол: {gender_text}")
        
        # Return to premium search menu
        from user_profile_aiogram import get_search_preferences_text
        await callback.message.edit_text(
            get_search_preferences_text(user_id),
            reply_markup=get_search_settings_keyboard(user_id)
        )
        
    elif callback.data.startswith("premium_age_"):
        age = callback.data.replace("premium_age_", "")
        age_text = {"any": "Любой", "7_17": "7-17", "18_25": "18-25", "26_35": "26-35", "36_50": "36-50", "50_plus": "50+"}.get(age, "Любой")
        
        # Save preference
        from user_profile_aiogram import set_search_preference, get_search_settings_keyboard, get_search_preferences_text
        set_search_preference(user_id, 'age_range', age)
        
        await callback.answer(f"Выбран возраст: {age_text}")
        
        # Return to premium search menu
        await callback.message.edit_text(
            get_search_preferences_text(user_id),
            reply_markup=get_search_settings_keyboard(user_id)
        )
        
    elif callback.data.startswith("premium_country_"):
        country = callback.data.replace("premium_country_", "")
        country_text = {
            "all": "Все страны",
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
        }.get(country, "Все страны")
        
        # Handle multiple country selection
        from user_profile_aiogram import get_search_preference, set_search_preference, get_premium_country_keyboard
        
        if country == "all":
            # If "all" selected, clear other selections
            set_search_preference(user_id, 'countries', 'all')
            await callback.answer(f"Выбрано: {country_text}")
        else:
            # Toggle country selection
            selected_countries = get_search_preference(user_id, 'countries')
            selected_list = selected_countries.split(',') if selected_countries and selected_countries != 'all' else []
            
            if country in selected_list:
                # Remove country
                selected_list.remove(country)
                await callback.answer(f"Убрано: {country_text}")
            else:
                # Add country
                selected_list.append(country)
                await callback.answer(f"Добавлено: {country_text}")
            
            # Save updated list
            new_selection = ','.join(selected_list) if selected_list else ''
            set_search_preference(user_id, 'countries', new_selection)
        
        # Update keyboard with new selections
        await callback.message.edit_text(
            "🌍 **Выберите страны собеседника:**\n\n"
            "Можете выбрать несколько стран. Выбранные страны отмечены ✅",
            reply_markup=get_premium_country_keyboard(user_id)
        )
        
    elif callback.data.startswith("premium_type_"):
        user_type = callback.data.replace("premium_type_", "")
        type_text = {"all": "Все пользователи", "premium": "Только Premium", "regular": "Только обычные"}.get(user_type, "Все пользователи")
        
        # Save preference
        from user_profile_aiogram import set_search_preference, get_search_settings_keyboard
        set_search_preference(user_id, 'user_type', user_type)
        
        await callback.answer(f"Выбран тип: {type_text}")
        
        # Return to premium search menu
        from user_profile_aiogram import get_search_preferences_text
        await callback.message.edit_text(
            get_search_preferences_text(user_id),
            reply_markup=get_search_settings_keyboard(user_id)
        )
        
    elif callback.data == "premium_toggle_show_status":
        # Toggle show premium status
        from user_profile_aiogram import get_search_preference, set_search_preference, get_premium_show_status_keyboard
        
        current_status = get_search_preference(user_id, 'show_premium_status')
        new_status = 'false' if current_status != 'false' else 'true'
        set_search_preference(user_id, 'show_premium_status', new_status)
        
        status_text = "включен" if new_status == 'true' else "выключен"
        await callback.answer(f"Показ Premium статуса {status_text}")
        
        # Update keyboard
        await callback.message.edit_text(
            "💎 **Показывать Premium статус:**\n\n"
            "Если включено, собеседники будут видеть что вы Premium пользователь.",
            reply_markup=get_premium_show_status_keyboard(user_id)
        )

async def handle_registration_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle registration callbacks"""
    from bot_aiogram import RegistrationStates
    
    if callback.data == "reg_gender_male":
        await state.update_data(gender="👨 Чоловік")
        await callback.answer("Обрано: Чоловік")
        await callback.message.edit_text("2. Введіть ваш вік (від 7 до 99 років):")
        await state.set_state(RegistrationStates.waiting_for_age)
        
    elif callback.data == "reg_gender_female":
        await state.update_data(gender="👩 Жінка")
        await callback.answer("Обрано: Жінка")
        await callback.message.edit_text("2. Введіть ваш вік (від 7 до 99 років):")
        await state.set_state(RegistrationStates.waiting_for_age)

async def handle_country_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle country selection during registration"""
    from registration_aiogram import save_user
    import time
    
    country_map = {
        "country_ukraine": "🇺🇦 Україна",
        "country_russia": "🇷🇺 Росія", 
        "country_belarus": "🇧🇾 Білорусь",
        "country_kazakhstan": "🇰🇿 Казахстан",
        "country_georgia": "🇬🇪 Грузія",
        "country_europe": "🇪🇺 Європа",
        "country_azerbaijan": "🇦🇿 Азербайджан",
        "country_uzbekistan": "🇺🇿 Узбекистан",
        "country_usa": "🇺🇸 США",
        "country_thailand": "🇹🇭 Тайланд",
        "country_english": "🇬🇧 English",
        "country_other": "🌎 Решта світу"
    }
    
    country = country_map.get(callback.data)
    if not country:
        await callback.answer("Невідома країна")
        return
        
    await state.update_data(country=country)
    await callback.answer(f"Обрано: {country}")
    
    # Registration completed - save user
    data = await state.get_data()
    user_id = callback.from_user.id
    
    save_user(
        user_id=user_id,
        gender=data['gender'],
        age=data['age'],
        country=country,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name
    )
    
    await callback.message.edit_text("✅ Реєстрація завершена! Ласкаво просимо!")
    
    # Get main keyboard
    from bot_aiogram import get_main_keyboard
    await callback.message.answer(
        "Тепер ви можете почати пошук співрозмовника!",
        reply_markup=get_main_keyboard()
    )
    
    # Process referral if exists
    if 'referrer_id' in data:
        referrer_id = data['referrer_id']
        from bot_aiogram import process_referral
        await process_referral(referrer_id, user_id)
    
    await state.clear()

async def handle_profile_edit_actions(callback: types.CallbackQuery):
    """Handle profile edit action callbacks"""
    user_id = callback.from_user.id
    
    # Gender setting
    if callback.data == "set_gender_male":
        update_user_gender(user_id, "👨 Чоловік")
        await callback.answer("Пол изменен на мужской")
        profile_text = format_combined_profile(user_id, is_premium)
        from user_profile_aiogram import get_profile_edit_inline_keyboard
        await callback.message.edit_text(profile_text, reply_markup=get_profile_edit_inline_keyboard())
        
    elif callback.data == "set_gender_female":
        update_user_gender(user_id, "👩 Жінка")
        await callback.answer("Пол изменен на женский")
        profile_text = format_combined_profile(user_id, is_premium)
        from user_profile_aiogram import get_profile_edit_inline_keyboard
        await callback.message.edit_text(profile_text, reply_markup=get_profile_edit_inline_keyboard())
        
    # Age setting is now handled by text input, not buttons
        
    # Country setting
    elif callback.data.startswith("set_country_"):
        country_map = {
            "set_country_ukraine": "🇺🇦 Україна",
            "set_country_russia": "🇷🇺 Росія",
            "set_country_belarus": "🇧🇾 Білорусь",
            "set_country_kazakhstan": "🇰🇿 Казахстан",
            "set_country_georgia": "🇬🇪 Грузія",
            "set_country_europe": "🇪🇺 Європа",
            "set_country_azerbaijan": "🇦🇿 Азербайджан",
            "set_country_uzbekistan": "🇺🇿 Узбекистан",
            "set_country_usa": "🇺🇸 США",
            "set_country_thailand": "🇹🇭 Тайланд",
            "set_country_english": "🇬🇧 English",
            "set_country_other": "🌎 Решта світу"
        }
        
        country = country_map.get(callback.data)
        if country:
            update_user_country(user_id, country)
            await callback.answer(f"Страна изменена на {country}")
            profile_text = format_combined_profile(user_id, is_premium)
            from user_profile_aiogram import get_profile_edit_inline_keyboard
            await callback.message.edit_text(profile_text, reply_markup=get_profile_edit_inline_keyboard())
            
    # Media blur toggle setting
    elif callback.data == "toggle_blur_on":
        update_media_blur(user_id, True)
        await callback.answer("✅ Блюр фото/видео включено")
        
        # Update the blur settings page with new status
        blur_status = True
        info_text = (
            "🙈 **Скрить фото/видео**\n\n"
            "📷 Ця функція дозволяє скрити всі фото та відео, які ви отримуєте від співрозмовників.\n\n"
            "✅ **Включено**: всі медіа будуть заблюровані\n"
            "❌ **Вимкнено**: медіа будуть показані без блюру\n\n"
            f"🔄 **Поточний статус**: включено"
        )
        await callback.message.edit_text(info_text, reply_markup=get_media_blur_keyboard(blur_status))
        
    elif callback.data == "toggle_blur_off":
        update_media_blur(user_id, False)
        await callback.answer("❌ Блюр фото/видео вимкнено")
        
        # Update the blur settings page with new status
        blur_status = False
        info_text = (
            "🙈 **Скрить фото/видео**\n\n"
            "📷 Ця функція дозволяє скрити всі фото та відео, які ви отримуєте від співрозмовників.\n\n"
            "✅ **Включено**: всі медіа будуть заблюровані\n"
            "❌ **Вимкнено**: медіа будуть показані без блюру\n\n"
            f"🔄 **Поточний статус**: вимкнено"
        )
        await callback.message.edit_text(info_text, reply_markup=get_media_blur_keyboard(blur_status))

# Main callback handler
async def handle_callback_query(callback: types.CallbackQuery, state: FSMContext):
    """Main callback query handler"""
    try:
        # Rating callbacks
        if callback.data.startswith("rate_"):
            await handle_rating_callback(callback)
            
        # Next partner callback
        elif callback.data == "next":
            await handle_next_callback(callback)
            
            
        # Premium callbacks
        elif callback.data in ["get_premium", "free_premium", "premium_menu", "activate_referral_reward"] or callback.data.startswith("buy_"):
            await handle_premium_callback(callback)
            
        # PRO callbacks
        elif callback.data in ["show_pro_purchase", "back_to_premium", "buy_pro_month"]:
            await handle_pro_callbacks(callback)
            
        # Profile callbacks
        elif callback.data.startswith("profile_") or callback.data in ["edit_gender", "edit_age", "edit_country", "toggle_media_blur", "reset_ratings_stars", "invite_friend", "back_to_profile"]:
            await handle_profile_callback(callback, state)
            
        # Profile edit action callbacks
        elif callback.data.startswith(("set_gender_", "set_age_", "set_country_", "toggle_blur_")):
            await handle_profile_edit_actions(callback)
            
        # Search settings callbacks
        elif callback.data.startswith("search_"):
            await handle_search_settings_callback(callback)
            
        # Report callbacks
        elif callback.data.startswith("report_"):
            await handle_report_callback(callback)
            
        # Room callbacks
        elif callback.data.startswith("room_"):
            await handle_room_callback(callback)
            
        # Registration callbacks
        elif callback.data.startswith("reg_"):
            await handle_registration_callback(callback, state)
            
        # Country selection during registration
        elif callback.data.startswith("country_"):
            await handle_country_callback(callback, state)
            
        # Premium search callbacks
        elif callback.data.startswith("premium_"):
            await handle_premium_search_callback(callback, state)
            
        # Return to partner callback
        elif callback.data.startswith("return_to_"):
            await handle_return_to_partner(callback)
            
        # Return button callback (after rating)
        elif callback.data.startswith("return_"):
            await handle_return_callback(callback)
            
        # Return request response callbacks
        elif callback.data.startswith("return_accept_") or callback.data.startswith("return_decline_"):
            await handle_return_response(callback)
            
        # Friends system callbacks
        elif callback.data.startswith("add_friend_"):
            await handle_add_friend_callback(callback, state)
        elif callback.data.startswith("friend_info_"):
            await handle_friend_info_callback(callback)
        elif callback.data.startswith("friend_delete_"):
            await handle_friend_delete_callback(callback)
        elif callback.data.startswith("confirm_delete_"):
            await handle_confirm_delete_callback(callback)
        elif callback.data.startswith("friends_page_"):
            await handle_friends_page_callback(callback)
        elif callback.data == "friends_list":
            await handle_friends_list_callback(callback)
        elif callback.data == "friends_back":
            await handle_friends_back_callback(callback)
        elif callback.data.startswith("friend_request_"):
            await handle_friend_request_callback(callback)
        elif callback.data.startswith("friend_account_"):
            await handle_friend_account_callback(callback)
        elif callback.data.startswith("friend_activity_"):
            await handle_friend_activity_callback(callback)
        elif callback.data == "check_subscriptions":
            await handle_check_subscriptions_callback(callback)
            
        # PRO menu callbacks
        elif callback.data.startswith("pro_") or callback.data == "back_to_pro_menu":
            await handle_pro_menu_callback(callback)
            
        # Unblock payment callbacks
        elif callback.data.startswith("unblock_pay_"):
            await handle_unblock_payment_callback(callback)
            
        else:
            await callback.answer("Невідома команда")
            
    except Exception as e:
        print(f"Error in callback handler: {e}")
        await callback.answer("Сталася помилка. Спробуйте ще раз.")

async def handle_return_callback(callback: types.CallbackQuery):
    """Handle return button after rating"""
    user_id = callback.from_user.id
    
    # Return to main menu
    from bot_aiogram import get_main_keyboard
    keyboard = get_main_keyboard(user_id)
    
    await callback.message.edit_text(
        "🏠 Головне меню\n\nОберіть дію:",
        reply_markup=keyboard
    )

async def handle_return_to_partner(callback: types.CallbackQuery):
    """Handle return to partner request"""
    user_id = callback.from_user.id
    partner_id = int(callback.data.replace("return_to_", ""))
    
    # Check if user has premium or pro
    from premium_aiogram import is_premium, is_pro
    if not (is_premium(user_id) or is_pro(user_id)):
        await callback.answer("❌ Ця функція доступна тільки преміум/PRO користувачам!", show_alert=True)
        return
    
    # Check if partner is currently searching
    from chat_aiogram import is_waiting
    if is_waiting(partner_id):
        # Partner is searching - they will be connected automatically when search completes
        # Create return request in database
        from friends_system import create_return_request
        success, message = create_return_request(user_id, partner_id)
        
        if success:
            await callback.message.edit_text("⏳ Зачекайте, чекаємо співрозмовника...")
            await callback.answer("Запит створено, очікуйте з'єднання")
        else:
            await callback.answer(f"❌ {message}", show_alert=True)
    else:
        # Partner is not searching - create return request and wait
        from friends_system import create_return_request
        success, message = create_return_request(user_id, partner_id)
        
        if success:
            await callback.message.edit_text("⏳ Зачекайте, чекаємо співрозмовника...\n\nКоли ваш співрозмовник почне пошук, ви автоматично з'єднаєтесь.")
            await callback.answer("Запит створено, очікуйте з'єднання")
        else:
            await callback.answer(f"❌ {message}", show_alert=True)

async def handle_return_response(callback: types.CallbackQuery):
    """Handle response to return request"""
    user_id = callback.from_user.id
    
    if callback.data.startswith("return_accept_"):
        requester_id = int(callback.data.replace("return_accept_", ""))
        
        # Check if both users are available for chat
        from chat_aiogram import get_partner, add_active, is_waiting, remove_waiting
        
        # Check if users are not already in other chats
        if get_partner(user_id) or get_partner(requester_id):
            await callback.message.edit_text("❌ Один з користувачів вже у чаті з кимось іншим.")
            await callback.answer("Не вдалося з'єднатися")
            return
        
        # Remove from waiting if they were searching
        if is_waiting(user_id):
            remove_waiting(user_id)
        if is_waiting(requester_id):
            remove_waiting(requester_id)
        
        # Connect users
        add_active(user_id, requester_id)
        
        # Notify both users
        await callback.message.edit_text("✅ Ви прийняли запрошення! Діалог відновлено.")
        
        try:
            from bot_aiogram import bot
            await bot.send_message(
                requester_id,
                "✅ Ваш запит прийнято! Діалог відновлено. 💎"
            )
        except Exception as e:
            print(f"Error notifying requester {requester_id}: {e}")
            
        await callback.answer("✅ Діалог відновлено!")
        
    elif callback.data.startswith("return_decline_"):
        requester_id = int(callback.data.replace("return_decline_", ""))
        
        # Notify both users
        await callback.message.edit_text("❌ Ви відмовилися від запрошення.")
        
        try:
            from bot_aiogram import bot
            await bot.send_message(
                requester_id,
                "❌ Ваш запит на повернення було відхилено."
            )
        except Exception as e:
            print(f"Error notifying requester {requester_id}: {e}")
            
        await callback.answer("Запит відхилено")

async def handle_add_friend_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle add friend callback"""
    user_id = callback.from_user.id
    friend_id = int(callback.data.replace("add_friend_", ""))
    
    # Check PRO status
    from premium_aiogram import is_pro
    if not is_pro(user_id):
        await callback.answer("❌ Ця функція доступна тільки PRO користувачам!", show_alert=True)
        return
    
    # Get friend info
    from registration_aiogram import get_user
    friend_data = get_user(friend_id)
    if not friend_data:
        await callback.answer("❌ Користувача не знайдено", show_alert=True)
        return
    
    # Ask for friend name
    await callback.message.edit_text(
        f"👤 **Додавання в друзі**\n\n"
        f"Користувач: {friend_data.get('first_name', 'Невідомо')} "
        f"(@{friend_data.get('username', 'немає')})\n\n"
        f"Введіть ім'я для цього друга:"
    )
    
    # Store friend_id in state
    await state.update_data(adding_friend_id=friend_id)
    # Import FriendStates from the main bot file to avoid conflicts
    from bot_aiogram import FriendStates
    await state.set_state(FriendStates.waiting_for_name)
    
    # Log state setting for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Set state FriendStates.waiting_for_name for user {user_id}, friend_id: {friend_id}")
    
    await callback.answer()

async def handle_friend_info_callback(callback: types.CallbackQuery):
    """Handle friend info callback"""
    friend_id = int(callback.data.replace("friend_info_", ""))
    from friends_system import show_friend_info
    await show_friend_info(callback, friend_id)

async def handle_friends_page_callback(callback: types.CallbackQuery):
    """Handle friends page navigation"""
    page = int(callback.data.replace("friends_page_", ""))
    from friends_system import show_friends_list
    await show_friends_list(callback, page)

async def handle_friends_list_callback(callback: types.CallbackQuery):
    """Handle back to friends list"""
    from friends_system import show_friends_list
    await show_friends_list(callback)

async def handle_friends_back_callback(callback: types.CallbackQuery):
    """Handle back from friends list to main menu"""
    await callback.message.delete()
    await callback.answer("Повернення до головного меню")
    
    # Send main menu
    from bot_aiogram import get_main_keyboard
    await callback.message.answer(
        "Головне меню:",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )


async def handle_friend_account_callback(callback: types.CallbackQuery):
    """Handle get friend account callback"""
    friend_id = int(callback.data.replace("friend_account_", ""))
    
    # Create universal link using user_id (works regardless of username changes)
    account_link = f"tg://user?id={friend_id}"
    
    # Send as message without auto-copying
    await callback.message.answer(
        f"👤 **Посилання на акаунт друга:**\n\n{account_link}\n\n"
        f"💡 Це універсальне посилання, яке працює навіть якщо користувач змінить свій username."
    )
    
    await callback.answer("Посилання надіслано")

async def handle_friend_activity_callback(callback: types.CallbackQuery):
    """Handle friend activity notification callback"""
    user_id = callback.from_user.id
    friend_id = int(callback.data.replace("friend_activity_", ""))
    
    # Toggle notification status
    from friends_system import toggle_activity_notification, get_user_activity, show_friend_info
    
    is_enabled = toggle_activity_notification(user_id, friend_id)
    
    if is_enabled:
        await callback.answer("✅ Повідомлення про активність увімкнено")
    else:
        await callback.answer("❌ Повідомлення про активність вимкнено")
    
    # Refresh friend info to show updated button
    await show_friend_info(callback, friend_id)

async def handle_pro_menu_callback(callback: types.CallbackQuery):
    """Handle PRO menu callbacks"""
    user_id = callback.from_user.id
    
    # Check PRO status
    from premium_aiogram import is_pro
    if not is_pro(user_id):
        await callback.answer("❌ Ця функція доступна тільки PRO користувачам!", show_alert=True)
        return
    
    if callback.data == "pro_friends":
        # Show friends list
        from friends_system import show_friends_list
        await show_friends_list(callback)
        
        
    elif callback.data == "pro_about":
        # Show PRO status info
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
            minutes = (remaining_seconds % 3600) // 60
            
            if days > 0:
                time_left = f"{days} дн. {hours} год. {minutes} хв."
            elif hours > 0:
                time_left = f"{hours} год. {minutes} хв."
            else:
                time_left = f"{minutes} хв."
        else:
            time_left = "Назавжди"
        
        from datetime import datetime
        if pro_until > 0 and remaining_seconds > 0:
            end_date = datetime.fromtimestamp(pro_until)
            end_date_text = end_date.strftime('%d.%m.%Y %H:%M')
        else:
            end_date_text = "Назавжди"
        
        about_text = (
            f"🌟 *Про ваш PRO статус*\n\n"
            f"📅 *Закінчується:* {end_date_text}\n"
            f"⏰ *Залишилось:* {time_left}\n\n"
            f"🎯 *PRO можливості:*\n"
            f"• 👥 Система друзів з детальними профілями\n"
            f"• 📞 Швидкі запроси на розмову з друзями\n"
            f"• 🔔 Відстеження активності друзів\n"
            f"• 👤 Пряме посилання на акаунти друзів\n"
            f"• 🔄 Повернення до попереднього співрозмовника\n"
            f"• 💎 Всі функції Premium статусу\n\n"
            f"✨ *Ексклюзивні PRO функції недоступні іншим користувачам!*"
        )
        
        back_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад до PRO меню", callback_data="back_to_pro_menu")]]
        )
        
        await callback.message.edit_text(about_text, reply_markup=back_keyboard)
        await callback.answer()
        
    elif callback.data == "back_to_pro_menu":
        # Return to main PRO menu
        from bot_aiogram import pro_command
        # Recreate the main PRO menu
        await callback.message.delete()
        
        # Create a fake message object to reuse pro_command logic
        class FakeMessage:
            def __init__(self, user_id):
                self.from_user = types.User(id=user_id, is_bot=False, first_name="User")
            
            async def answer(self, text, reply_markup=None):
                await callback.message.answer(text, reply_markup=reply_markup)
        
        fake_message = FakeMessage(user_id)
        await pro_command(fake_message)
        await callback.answer()
        
    else:
        await callback.answer("Функція в розробці", show_alert=True)

async def handle_friend_request_callback(callback: types.CallbackQuery):
    """Handle friend request callback"""
    friend_id = int(callback.data.replace("friend_request_", ""))
    user_id = callback.from_user.id
    
    from friends_system import send_friend_request
    success, message = send_friend_request(user_id, friend_id)
    
    if success:
        await callback.answer("✅ Запрос на розмову надіслано!", show_alert=True)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

async def handle_friend_delete_callback(callback: types.CallbackQuery):
    """Handle friend delete callback"""
    friend_id = int(callback.data.replace("friend_delete_", ""))
    user_id = callback.from_user.id
    
    # Get friend's name for confirmation
    from friends_system import get_friend_name, delete_friend
    friend_name = get_friend_name(user_id, friend_id)
    
    # Create confirmation keyboard
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"confirm_delete_{friend_id}"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data=f"friend_info_{friend_id}")
            ]
        ]
    )
    
    await callback.message.edit_text(
        f"🗑️ **Видалення друга**\n\n"
        f"Ви впевнені, що хочете видалити **{friend_name}** зі списку друзів?\n\n"
        f"⚠️ Цю дію неможливо скасувати.",
        reply_markup=confirm_keyboard
    )
    await callback.answer()

async def handle_confirm_delete_callback(callback: types.CallbackQuery):
    """Handle confirm delete friend callback"""
    friend_id = int(callback.data.replace("confirm_delete_", ""))
    user_id = callback.from_user.id
    
    from friends_system import get_friend_name, delete_friend, show_friends_list
    friend_name = get_friend_name(user_id, friend_id)
    
    if delete_friend(user_id, friend_id):
        await callback.message.edit_text(
            f"✅ **Друга видалено**\n\n"
            f"**{friend_name}** успішно видалено зі списку друзів."
        )
        
        # Wait a moment then show friends list
        import asyncio
        await asyncio.sleep(2)
        await show_friends_list(callback)
    else:
        await callback.message.edit_text(
            f"❌ **Помилка**\n\n"
            f"Не вдалося видалити друга. Спробуйте пізніше."
        )
    
    await callback.answer()

async def handle_check_subscriptions_callback(callback: types.CallbackQuery):
    """Handle check subscriptions callback"""
    from complaints_system import check_user_subscriptions
    from bot_aiogram import bot
    
    user_id = callback.from_user.id
    
    # Check if user is subscribed to all required channels
    is_subscribed = await check_user_subscriptions(user_id, bot)
    
    if is_subscribed:
        await callback.message.edit_text(
            "✅ **Підписка підтверджена!**\n\n"
            "Дякуємо за підписку на всі обов'язкові канали.\n"
            "Тепер ви можете повноцінно користуватися ботом!\n\n"
            "Натисніть /start для продовження."
        )
    else:
        from complaints_system import create_subscription_keyboard
        
        keyboard = create_subscription_keyboard()
        await callback.message.edit_text(
            "❌ **Підписка не підтверджена**\n\n"
            "Будь ласка, підпишіться на всі обов'язкові канали та спробуйте знову:",
            reply_markup=keyboard
        )
    
    await callback.answer()

# PRO system callback handlers
async def handle_pro_callbacks(callback: types.CallbackQuery):
    """Handle PRO-related callbacks"""
    if callback.data == "show_pro_purchase":
        from premium_aiogram import show_pro_purchase
        await show_pro_purchase(callback)
    elif callback.data == "back_to_premium":
        from premium_aiogram import back_to_premium
        await back_to_premium(callback)
    elif callback.data == "buy_pro_month":
        from premium_aiogram import start_premium_purchase
        await start_premium_purchase(callback)

async def handle_unblock_payment_callback(callback: types.CallbackQuery):
    """Handle unblock payment callback"""
    user_id = callback.from_user.id
    
    # Check if user is actually blocked
    from registration_aiogram import is_user_blocked
    if not is_user_blocked(user_id):
        await callback.message.edit_text(
            "✅ **Ваш акаунт не заблокований**\n\n"
            "Ви можете вільно користуватися ботом!"
        )
        await callback.answer()
        return
    
    # Create payment invoice for 99 stars
    from aiogram.types import LabeledPrice
    
    try:
        prices = [LabeledPrice(label="Розблокування акаунту", amount=99)]
        
        await callback.bot.send_invoice(
            chat_id=user_id,
            title="🔓 Розблокування акаунту",
            description="Миттєве розблокування вашого акаунту за 99⭐",
            payload="unblock_account",
            provider_token="",  # For Telegram Stars, provider_token should be empty
            currency="XTR",  # Telegram Stars currency
            prices=prices,
            start_parameter="unblock_payment"
        )
        
        await callback.message.edit_text(
            "💳 **Рахунок створено!**\n\n"
            "📋 **Деталі платежу:**\n"
            "• Послуга: Розблокування акаунту\n"
            "• Вартість: 99⭐\n"
            "• Тип: Миттєве розблокування\n\n"
            "💡 **Після оплати ваш акаунт буде автоматично розблокований!**"
        )
        
    except Exception as e:
        print(f"Error creating unblock invoice: {e}")
        await callback.message.edit_text(
            "❌ **Помилка створення рахунку**\n\n"
            "Не вдалося створити рахунок для оплати.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )
    
    await callback.answer()

# States for friends system are defined in bot_aiogram.py

# Register callback handlers
def register_callback_handlers(dp):
    """Register all callback handlers"""
    dp.callback_query.register(handle_callback_query)
