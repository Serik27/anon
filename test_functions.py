#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки основних функцій бота
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from friends_system import (
    get_user_activity, 
    update_user_activity,
    create_chat_request,
    get_pending_request_for_user,
    accept_chat_request
)
from registration_aiogram import get_conn

def test_user_activity():
    """Тест системи активності користувачів"""
    print("Тестування системи активності користувачів...")
    
    test_user_id = 12345
    
    # Оновлюємо активність користувача
    update_user_activity(test_user_id, is_chatting=True)
    
    # Перевіряємо активність
    activity = get_user_activity(test_user_id)
    
    print(f"Активність користувача {test_user_id}:")
    print(f"   - Онлайн: {activity['is_online']}")
    print(f"   - Активний в боті: {activity['is_bot_active']}")
    print(f"   - Спілкується: {activity['is_chatting']}")
    
    return activity['is_online'] and activity['is_bot_active'] and activity['is_chatting']

def test_chat_requests():
    """Тест системи запросів на розмову"""
    print("\nТестування системи запросів на розмову...")
    
    pro_user_id = 11111
    regular_user_id = 22222
    
    # Створюємо запрос
    success, message = create_chat_request(pro_user_id, regular_user_id)
    print(f"Створення запросу: {success} - {message}")
    
    # Перевіряємо наявність запросу
    pending_request = get_pending_request_for_user(regular_user_id)
    print(f"Знайдено запрос від користувача: {pending_request}")
    
    # Приймаємо запрос
    if pending_request:
        accept_chat_request(pro_user_id, regular_user_id)
        print("Запрос прийнято")
    
    return success and pending_request == pro_user_id

def test_database_tables():
    """Перевірка наявності необхідних таблиць"""
    print("\nПеревірка таблиць бази даних...")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Перевіряємо таблиці
    tables_to_check = [
        'users', 'user_activity', 'friends', 'chat_requests'
    ]
    
    existing_tables = []
    for table in tables_to_check:
        cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if cur.fetchone():
            existing_tables.append(table)
            print(f"OK: Таблиця '{table}' існує")
        else:
            print(f"ERROR: Таблиця '{table}' не знайдена")
    
    conn.close()
    return len(existing_tables) == len(tables_to_check)

def main():
    """Основна функція тестування"""
    print("Запуск тестів функціональності бота...\n")
    
    tests = [
        ("Перевірка таблиць БД", test_database_tables),
        ("Система активності", test_user_activity),
        ("Система запросів", test_chat_requests)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            status = "ПРОЙДЕНО" if result else "ПРОВАЛЕНО"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            results.append((test_name, False))
            print(f"\nПОМИЛКА в {test_name}: {e}")
    
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТИ ТЕСТУВАННЯ:")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "OK" if result else "ERROR"
        print(f"{status}: {test_name}")
    
    print(f"\nПройдено: {passed}/{total} тестів")
    
    if passed == total:
        print("Всі тести пройдено успішно!")
    else:
        print("Деякі тести провалилися. Перевірте помилки вище.")

if __name__ == "__main__":
    main()
