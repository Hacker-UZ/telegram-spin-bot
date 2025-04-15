import time
import telebot
from telebot import apihelper
from config import ADMIN_ID, BOT_TOKEN
from database import init_db
from handlers.user_handlers import setup_user_handlers
from handlers.payment_handler import setup_payment_handler  
from handlers.admin_handlers import setup_admin_handlers
from keep_alive import keep_alive
keep_alive()

def main():
    # Enable middleware
    apihelper.ENABLE_MIDDLEWARE = True

    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Initialize the bot
    bot = telebot.TeleBot(BOT_TOKEN)
    setup_user_handlers(bot)
    setup_payment_handler(bot, ADMIN_ID)
    setup_admin_handlers(bot, ADMIN_ID)
    
    print("Bot ishga tushdi...")

    # Retry mechanism for infinity_polling
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(5)  # Wait before retrying

if __name__ == '__main__':
    main()