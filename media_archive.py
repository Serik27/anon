import os
import time
import sqlite3
import logging
from collections import defaultdict
from typing import List

from aiogram import types

logger = logging.getLogger(__name__)

MEDIA_DB_PATH = 'media_store.db'
FILTER_WORDS_FILE = 'filter_words.txt'
MEDIA_ARCHIVE_CHANNEL_ID = int(os.getenv('MEDIA_ARCHIVE_CHANNEL_ID', '0') or '0')

def ensure_media_db():
    conn = sqlite3.connect(MEDIA_DB_PATH)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS saved_media (
        file_id TEXT PRIMARY KEY,
        sender_id INTEGER
    )
    ''')
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

def load_filter_words() -> List[str]:
    try:
        if os.path.exists(FILTER_WORDS_FILE):
            with open(FILTER_WORDS_FILE, 'r', encoding='utf-8') as f:
                return [w.strip().lower() for w in f if w.strip() and not w.strip().startswith('#')]
    except Exception as e:
        logger.warning(f"Failed to read {FILTER_WORDS_FILE}: {e}")
    return []

# Conversation buffer shared across modules
conversation_buffer: dict[frozenset, list] = defaultdict(list)

def _conv_key(u1: int, u2: int) -> frozenset:
    return frozenset({u1, u2})

def buffer_record_text(user_id: int, partner_id: int, text: str):
    try:
        conversation_buffer[_conv_key(user_id, partner_id)].append({
            'type': 'text',
            'ts': int(time.time()),
            'user_id': user_id,
            'text': text or ''
        })
        logger.info(f"Buffer text: users={[user_id, partner_id]} size={len(conversation_buffer[_conv_key(user_id, partner_id)])}")
    except Exception as e:
        logger.debug(f"buffer_record_text error: {e}")

def buffer_record_media(user_id: int, partner_id: int, media_type: str, file_id: str, caption: str | None):
    try:
        conversation_buffer[_conv_key(user_id, partner_id)].append({
            'type': 'media',
            'ts': int(time.time()),
            'user_id': user_id,
            'media_type': media_type,
            'file_id': file_id,
            'caption': caption or ''
        })
        logger.info(f"Buffer media: users={[user_id, partner_id]} type={media_type} file_id={file_id} size={len(conversation_buffer[_conv_key(user_id, partner_id)])}")
    except Exception as e:
        logger.debug(f"buffer_record_media error: {e}")

async def process_conversation_archive(bot, user_a: int, user_b: int):
    key = _conv_key(user_a, user_b)
    items = conversation_buffer.get(key, [])
    logger.info(f"Archive check: conv={list(key)}, items={len(items)}, channel_id={MEDIA_ARCHIVE_CHANNEL_ID}")
    if not items:
        conversation_buffer.pop(key, None)
        return
    words = load_filter_words()
    logger.info(f"Archive check: filter_words={len(words)}")
    if not words:
        conversation_buffer.pop(key, None)
        return
    try:
        text_parts = [(it.get('text') or '') for it in items if it['type'] == 'text']
        text_blob = "\n".join(text_parts).lower()
        has_keyword = any(w in text_blob for w in words)
        logger.info(f"Archive check: has_keyword={has_keyword}")
        if not has_keyword:
            conversation_buffer.pop(key, None)
            return
        ensure_media_db()
        seen = set()
        for it in items:
            if it['type'] != 'media':
                continue
            file_id = it['file_id']
            if not file_id or file_id in seen or is_media_saved(file_id):
                continue
            seen.add(file_id)
            base_caption = it.get('caption') or ''
            sender_info = f"\n🆔 Відправник: `{it['user_id']}`"
            try:
                if not MEDIA_ARCHIVE_CHANNEL_ID:
                    logger.warning("Archive skipped: MEDIA_ARCHIVE_CHANNEL_ID is not set")
                    continue
                if it['media_type'] == 'photo':
                    await bot.send_photo(MEDIA_ARCHIVE_CHANNEL_ID, photo=file_id, caption=(base_caption + sender_info))
                elif it['media_type'] == 'video':
                    await bot.send_video(MEDIA_ARCHIVE_CHANNEL_ID, video=file_id, caption=(base_caption + sender_info))
                elif it['media_type'] == 'video_note':
                    await bot.send_video_note(MEDIA_ARCHIVE_CHANNEL_ID, video_note=file_id)
                    await bot.send_message(MEDIA_ARCHIVE_CHANNEL_ID, f"🆔 Відправник: `{it['user_id']}`")
                else:
                    continue
                mark_media_saved(file_id, it['user_id'])
                logger.info(f"Archived media: type={it['media_type']} sender={it['user_id']} file_id={file_id}")
            except Exception as e:
                logger.warning(f"Archive after chat failed for {file_id}: {e}")
    finally:
        conversation_buffer.pop(key, None)


