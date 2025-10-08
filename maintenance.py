import time
from registration_aiogram import get_conn

DEFAULT_MAINTENANCE_MESSAGE = "🔧 Технічна перерва. Пошук тимчасово недоступний."
DEFAULT_RESTORED_MESSAGE = "✅ Бот відновив роботу. Пошук знову доступний."

def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    INSERT OR REPLACE INTO settings (key, value, updated_at)
    VALUES (?, ?, ?)
    ''', (key, value, int(time.time())))
    conn.commit()
    conn.close()

def get_setting(key: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def enable_maintenance(message: str | None = None):
    set_setting('maintenance_enabled', '1')
    set_setting('maintenance_message', message or DEFAULT_MAINTENANCE_MESSAGE)

def disable_maintenance():
    set_setting('maintenance_enabled', '0')
    set_setting('maintenance_restored_message', DEFAULT_RESTORED_MESSAGE)

def is_maintenance_enabled() -> bool:
    return (get_setting('maintenance_enabled') == '1')

def get_maintenance_message() -> str:
    return get_setting('maintenance_message') or DEFAULT_MAINTENANCE_MESSAGE

def get_restored_message() -> str:
    return get_setting('maintenance_restored_message') or DEFAULT_RESTORED_MESSAGE


