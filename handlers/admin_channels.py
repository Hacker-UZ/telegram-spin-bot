from telebot import types
from telebot.apihelper import ApiTelegramException
from datetime import datetime
import sqlite3

def format_money(amount):
    return f"{amount:,} so'm"

def validate_markdown(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def setup_admin_channels(bot_instance, admin_id):
    bot = bot_instance

    @bot.message_handler(func=lambda m: m.text == "📢 Kanallar" and m.from_user.id == admin_id)
    def handle_channels_menu(message):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(
            types.KeyboardButton("➕ Kanal qo'shish"),
            types.KeyboardButton("➖ Kanal olib tashlash")
        )
        keyboard.row(
            types.KeyboardButton("📋 Kanallar ro'yxati"),
            types.KeyboardButton("🔙 Qaytish")
        )
        bot.send_message(
            message.chat.id,
            "📢 *Majburiy kanallar boshqaruvi*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: m.text == "➕ Kanal qo'shish" and m.from_user.id == admin_id)
    def handle_add_channel(message):
        msg = bot.send_message(
            message.chat.id,
            "Kanal linkini yuboring:\n\n"
            "Misollar:\n"
            "• https://t.me/channel_name\n"
            "• t.me/channel_name\n"
            "@channel_name"
        )
        bot.register_next_step_handler(msg, process_add_channel)

    def process_add_channel(message):
        if message.text in ["📋 Kanallar ro'yxati", "➖ Kanal olib tashlash", "🔙 Admin menyusi"]:
            bot.send_message(
                message.chat.id,
                "❌ Iltimos, kanal linkini kiriting."
            )
            return

        channel_link = message.text.strip()
        
        try:
            # Link'ni to'g'ridan-to'g'ri saqlash
            # Private kanal link'larni ham qabul qilish: https://t.me/+gg8l4YzQ0DZlNmMy
            channel_id = channel_link
            channel_name = channel_link
            
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            # Link'ni bazaga saqlash
            cursor.execute(
                "INSERT OR REPLACE INTO channels (channel_id, channel_name, added_by, add_date) VALUES (?, ?, ?, ?)",
                (channel_id, channel_name, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            conn.commit()
            conn.close()
            
            bot.send_message(
                message.chat.id,
                f"✅ Kanal majburiy ro'yxatga qo'shildi:\n"
                f"🔗 Link: {channel_link}"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato: {str(e)}\n"
                f"Qayta urinib ko'ring."
            )

    @bot.message_handler(func=lambda m: m.text == "➖ Kanal olib tashlash" and m.from_user.id == admin_id)
    def handle_remove_channel(message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        channels = cursor.fetchall()
        conn.close()
        
        if not channels:
            bot.send_message(message.chat.id, "❌ Hozircha kanallar mavjud emas")
            return
        
        keyboard = types.InlineKeyboardMarkup()
        for channel_id, channel_name in channels:
            keyboard.add(types.InlineKeyboardButton(
                text=f"❌ {channel_name}",
                callback_data=f"remove_channel_{channel_id}"
            ))
        
        bot.send_message(
            message.chat.id,
            "📢 Majburiy ro'yxatdan olib tashlamoqchi bo'lgan kanalni tanlang:",
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_channel_'))
    def handle_remove_channel_callback(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        channel_id = call.data.split('remove_channel_')[-1]

        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT channel_name FROM channels WHERE channel_id=?", (channel_id,))
            result = cursor.fetchone()
            if not result:
                bot.answer_callback_query(call.id, "❌ Kanal topilmadi!")
                return

            channel_name = result[0]

            cursor.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
            cursor.execute("DELETE FROM user_subscriptions WHERE channel_id=?", (channel_id,))
            conn.commit()

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Kanal olib tashlandi: {channel_name}"
            )
            bot.answer_callback_query(call.id, "✅ Kanal muvaffaqiyatli olib tashlandi!")
        except Exception as e:
            conn.rollback()
            bot.answer_callback_query(call.id, f"❌ Xato: {str(e)}")
            print(f"Error removing channel: {e}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: m.text == "📋 Kanallar ro'yxati" and m.from_user.id == admin_id)
    def handle_list_channels(message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        channels = cursor.fetchall()
        conn.close()
        
        if not channels:
            bot.send_message(message.chat.id, "❌ Hozircha kanallar mavjud emas")
            return
        
        try:
            keyboard = types.InlineKeyboardMarkup()
            response = "📋 *Majburiy kanallar ro'yxati:*\n\n"
            
            for i, (channel_id, channel_name) in enumerate(channels, 1):
                response += f"{i}. {channel_name}\n"
                keyboard.add(types.InlineKeyboardButton(
                    text=f"🔗 O'tish",
                    url=channel_name
                ))
            
            response = validate_markdown(response)
            bot.send_message(message.chat.id, response, parse_mode="Markdown", reply_markup=keyboard)
        except ApiTelegramException as e:
            error_message = f"Failed to send message: {e.description}"
            bot.send_message(message.chat.id, error_message)
            print(error_message)

    @bot.message_handler(func=lambda m: m.text == "➕ Kanalni aktivlashtirish" and m.from_user.id == admin_id)
    def handle_activate_channel(message):
        try:
            bot_info = bot.get_me()
            bot_username = bot_info.username
            
            keyboard = types.InlineKeyboardMarkup()
            btn_add = types.InlineKeyboardButton(
                "➕ Bot'ni qo'shish",
                url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages+manage_topics"
            )
            keyboard.add(btn_add)
            
            bot.send_message(
                message.chat.id,
                "🔗 Bot'ni kanalga qo'shish uchun quyidagi tugmani bosing:\n\n"
                "❗ Bot'ni admin qilib qo'shishni unutmang!",
                reply_markup=keyboard
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato yuz berdi: {str(e)}"
            )
