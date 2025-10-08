import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot

# Load environment variables
load_dotenv()

async def clear_webhook():
    """Clear webhook and check bot status"""
    bot = Bot(token=os.getenv('MAIN_BOT_TOKEN'))
    
    try:
        # Delete webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook видалено успішно")
        
        # Get bot info
        me = await bot.get_me()
        print(f"Бот активний: @{me.username}")
        
        # Get webhook info
        webhook_info = await bot.get_webhook_info()
        print(f"Webhook URL: {webhook_info.url or 'Не встановлено'}")
        print(f"Очікуючих оновлень: {webhook_info.pending_update_count}")
        
    except Exception as e:
        print(f"Помилка: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(clear_webhook())
