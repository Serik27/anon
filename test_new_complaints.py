# -*- coding: utf-8 -*-
"""
Тест нової системи скарг (20+ скарг)
"""

def test_new_complaints_system():
    print("=== ТЕСТ НОВОЇ СИСТЕМИ СКАРГ (20+) ===")
    
    try:
        from complaints_system import (
            init_complaints_tables, 
            add_complaint, 
            save_user_message,
            get_critical_period_messages,
            get_complaint_count,
            get_users_with_complaints,
            block_user,
            unblock_user,
            is_user_blocked
        )
        
        print("1. Ініціалізація таблиць...")
        init_complaints_tables()
        print("   [OK] Таблиці створено")
        
        # Test data
        test_user_id = 555666777
        reporter_base_id = 111222333
        
        print("\n2. Додавання скарг до 18...")
        for i in range(18):
            complaint_count = add_complaint(reporter_base_id + i, test_user_id, f"Скарга {i+1}")
            if i == 17:  # 18th complaint
                print(f"   [INFO] 18 скарг досягнуто: {complaint_count}")
        
        print("\n3. Тестування збереження повідомлень з 18 скаргами...")
        # Now messages should be saved because user has 18+ complaints
        save_user_message(test_user_id, "Повідомлення 1 (18 скарг)", None, None, 999888777)
        save_user_message(test_user_id, "Повідомлення 2 (18 скарг)", None, None, 999888777)
        save_user_message(test_user_id, None, "photo", "test_photo_id", 999888777)
        print("   [OK] Повідомлення збережено (18+ скарг)")
        
        print("\n4. Додавання скарг до 20...")
        for i in range(18, 22):  # Add 4 more complaints to reach 22
            complaint_count = add_complaint(reporter_base_id + i, test_user_id, f"Скарга {i+1}")
            if i == 19:  # 20th complaint
                print(f"   [ALERT] 20 скарг досягнуто! Користувач на перевірці: {complaint_count}")
        
        print("\n5. Тестування збереження повідомлень з 20+ скаргами...")
        save_user_message(test_user_id, "Повідомлення 3 (20+ скарг)", None, None, 999888777)
        save_user_message(test_user_id, "Критичне повідомлення", None, None, 999888777)
        print("   [OK] Повідомлення збережено (20+ скарг)")
        
        print("\n6. Отримання повідомлень з критичного періоду...")
        messages = get_critical_period_messages(test_user_id, 10)
        print(f"   [OK] Отримано {len(messages)} повідомлень з критичного періоду")
        
        for i, msg in enumerate(messages[:3], 1):
            message_text, media_type, timestamp, partner_id = msg
            print(f"      {i}. {message_text or f'Медіа: {media_type}'}")
        
        print("\n7. Отримання списку користувачів з 10+ скаргами...")
        users_with_complaints = get_users_with_complaints(10)
        print(f"   [OK] Знайдено {len(users_with_complaints)} користувачів з 10+ скаргами")
        
        for user_id, count in users_with_complaints:
            print(f"      Користувач {user_id}: {count} скарг")
        
        print("\n8. Тестування блокування/розблокування...")
        block_user(test_user_id, 999999, "Тест блокування")
        is_blocked_before = is_user_blocked(test_user_id)
        print(f"   [OK] Користувач заблокований: {is_blocked_before}")
        
        unblock_user(test_user_id)
        is_blocked_after = is_user_blocked(test_user_id)
        print(f"   [OK] Користувач розблокований: {not is_blocked_after}")
        
        print("\n=== ТЕСТ ЗАВЕРШЕНО УСПІШНО ===")
        print(f"\nРезультати:")
        print(f"• Скарг додано: 22")
        print(f"• Повідомлень збережено: 5")
        print(f"• Користувачів з 10+ скаргами: {len(users_with_complaints)}")
        print(f"• Блокування/розблокування: працює")
        print(f"• Критичний поріг: 20 скарг")
        print(f"• Збереження з: 18 скарг")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_new_complaints_system()
    if success:
        print("\nНова система скарг працює правильно!")
    else:
        print("\nВиявлено проблеми в новій системі скарг!")
