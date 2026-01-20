from telebot import types
from datetime import datetime
import sqlite3
import telebot
from telebot.apihelper import ApiTelegramException
import os
from telebot.types import Message
import xlsxwriter 
from config import MIN_WITHDRAWAL, INITIAL_SPINS, REFERAL_SPINS, PRIZES, ADMIN_ID

def format_money(amount):
    return f"{amount:,} so'm"

def validate_markdown(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def setup_admin_handlers(bot_instance, admin_id):
    global bot
    bot = bot_instance
    
    import threading
    import time
    
    def send_db_backup():
        """Har 10 daqiqada database faylini adminga yuborish"""
        while True:
            try:
                time.sleep(600)  # 10 daqiqa
                db_path = 'pul_yutish.db'
                if os.path.exists(db_path):
                    with open(db_path, 'rb') as db_file:
                        bot.send_document(admin_id, db_file, caption="📊 Avtomatik DB backup")
            except Exception as e:
                print(f"DB backup xatosi: {e}")
    
    # Database backup thread'ni ishga tushirish
    backup_thread = threading.Thread(target=send_db_backup, daemon=True)
    backup_thread.start()

    @bot.message_handler(commands=['admin'])
    def handle_admin(message):
        if message.from_user.id != admin_id:
            bot.send_message(message.chat.id, "❌ Sizga ruxsat yo'q!")
            return
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("📊 Statistika")
        btn2 = types.KeyboardButton("💸 To'lov so'rovlari")
        btn3 = types.KeyboardButton("📢 Kanallar")
        btn4 = types.KeyboardButton("👥 Foydalanuvchilar")
        btn6 = types.KeyboardButton("📢 Xabar yuborish")
        btn7 = types.KeyboardButton("🔄 Hisobni 0 qilish")
        btn9 = types.KeyboardButton("🎁 Bonus berish")
        btn10 = types.KeyboardButton("➕ Kanalni aktivlashtirish")
        btn8 = types.KeyboardButton("🔙 Asosiy menyu")
        keyboard.row(btn1, btn2)
        keyboard.row(btn3, btn4)
        keyboard.row(btn6, btn7)
        keyboard.row(btn9, btn10)
        keyboard.row(btn8)
        
        bot.send_message(
            message.chat.id,
            "👑 *Admin paneli*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id == admin_id)
    def show_stats(message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals")
        total_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed'")
        total_payout = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM prizes")
        total_prizes = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")
        pending_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM channels")
        total_channels = cursor.fetchone()[0]
        
        conn.close()
        
        # Inline tugmalar foydalanuvchilar uchun
        keyboard = types.InlineKeyboardMarkup()
        btn_daily = types.InlineKeyboardButton("📅 Kunlik", callback_data="stats_daily")
        btn_weekly = types.InlineKeyboardButton("📆 Haftalik", callback_data="stats_weekly")
        btn_monthly = types.InlineKeyboardButton("📋 Oylik", callback_data="stats_monthly")
        keyboard.row(btn_daily, btn_weekly, btn_monthly)
        
        bot.send_message(
            message.chat.id,
            f"📊 *Bot statistikasi*\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"🤝 Jami referallar: {total_referals}\n"
            f"📢 Jami kanallar: {total_channels}\n"
            f"🎯 Jami yutqazilgan summa: {format_money(total_prizes)}\n"
            f"💰 Jami to'langan summa: {format_money(total_payout)}\n"
            f"⏳ Ko'rib chiqilishi kerak bo'lgan to'lovlar: {pending_payments}\n\n"
            f"👥 *Foydalanuvchilar ma'lumoti:*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
    def handle_stats_filter(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return
        
        filter_type = call.data.split('_')[1]  # daily, weekly, yoki monthly
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        # Vaqt filtri
        if filter_type == "daily":
            filter_text = "📅 *Kunlik foydalanuvchilar*"
            query = "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"
        elif filter_type == "weekly":
            filter_text = "📆 *Haftalik foydalanuvchilar*"
            query = "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')"
        else:  # monthly
            filter_text = "📋 *Oylik foydalanuvchilar*"
            query = "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-30 days')"
        
        cursor.execute(query)
        new_users = cursor.fetchone()[0]
        conn.close()
        
        keyboard = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Qaytish", callback_data="back_to_main_stats")
        keyboard.add(btn_back)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{filter_text}\n\n👥 Yangi foydalanuvchilar: {new_users}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_main_stats")
    def handle_back_to_main_stats(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return
        
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals")
        total_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed'")
        total_payout = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM prizes")
        total_prizes = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")
        pending_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM channels")
        total_channels = cursor.fetchone()[0]
        
        conn.close()
        
        keyboard = types.InlineKeyboardMarkup()
        btn_daily = types.InlineKeyboardButton("📅 Kunlik", callback_data="stats_daily")
        btn_weekly = types.InlineKeyboardButton("📆 Haftalik", callback_data="stats_weekly")
        btn_monthly = types.InlineKeyboardButton("📋 Oylik", callback_data="stats_monthly")
        keyboard.row(btn_daily, btn_weekly, btn_monthly)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📊 *Bot statistikasi*\n\n"
                 f"👥 Jami foydalanuvchilar: {total_users}\n"
                 f"🤝 Jami referallar: {total_referals}\n"
                 f"📢 Jami kanallar: {total_channels}\n"
                 f"🎯 Jami yutqazilgan summa: {format_money(total_prizes)}\n"
                 f"💰 Jami to'langan summa: {format_money(total_payout)}\n"
                 f"⏳ Ko'rib chiqilishi kerak bo'lgan to'lovlar: {pending_payments}\n\n"
                 f"👥 *Foydalanuvchilar ma'lumoti:*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.text == "💸 To'lov so'rovlari" and m.from_user.id == admin_id)
    def show_payment_requests(message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        cursor.execute('''SELECT p.id, u.username, u.phone_number, p.card_number, p.card_holder, p.amount, p.request_date 
                        FROM payments p
                        JOIN users u ON p.user_id = u.user_id
                        WHERE p.status='pending'
                        ORDER BY p.request_date DESC''')
        requests = cursor.fetchall()
        conn.close()

        if not requests:
            bot.send_message(message.chat.id, "⏳ Hozircha yangi to'lov so'rovlari mavjud emas.")
            return

        for req in requests:
            req_id, username, phone_number, card_number, card_holder, amount, req_date = req

            # Karta raqamini yashirib ko'rsatamiz
            masked_card = f"**** **** **** {card_number[-4:]}" if card_number and len(card_number) >= 4 else "Noma'lum"

            keyboard = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_pay_{req_id}")
            btn_reject = types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay_{req_id}")
            keyboard.add(btn_confirm, btn_reject)

            bot.send_message(
                message.chat.id,
                f"🆔 So'rov ID: {req_id}\n"
                f"👤 Foydalanuvchi: @{username}\n"
                f"📱 Telefon: {phone_number}\n"
                f"💰 Miqdor: {format_money(amount)}\n"
                f"💳 Karta raqami: {card_number}\n"
                f"👤 Karta egasi: {card_holder}\n"
                f"📅 Sana: {req_date}",
                reply_markup=keyboard
            )

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

    @bot_instance.message_handler(func=lambda m: m.text == "🔙 Admin menyusi" and m.from_user.id == admin_id)
    def back_to_admin_main_menu(message):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(
            types.KeyboardButton("📊 Statistika"),
            types.KeyboardButton("💸 To'lov so'rovlari"),
            types.KeyboardButton("📢 Kanallar")
        )
        keyboard.row(
            types.KeyboardButton("🔙 Asosiy menyu")
        )
        
        bot_instance.send_message(
            message.chat.id,
            "👑 *Admin paneli*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    # Kanalar menyusini yaratishda tugmani qo'shamiz
    @bot_instance.message_handler(func=lambda m: m.text == "📢 Kanallar" and m.from_user.id == admin_id)
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
        
        bot_instance.send_message(
            message.chat.id,
            "📢 *Majburiy kanallar boshqaruvi*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: m.text == "➕ Kanal qo'shish" and m.from_user.id == admin_id)
    def handle_add_channel(message):
        msg = bot.send_message(
            message.chat.id,
            "Yangi kanal qo'shish uchun kanal @username ni yuboring :\n\n"
            "Namuna: @channel_name\n\n"
            "❗ Kanalga bot admin qilinganligiga ishonch hosil qiling!"
        )
        bot.register_next_step_handler(msg, process_add_channel)

    def process_add_channel(message):
        if message.text in ["📋 Kanallar ro'yxati", "➖ Kanal olib tashlash", "🔙 Admin menyusi"]:
            bot.send_message(
                message.chat.id,
                "❌ Iltimos, avval kanal username yoki ID sini kiriting yoki boshqa tugmani bosmang."
            )
            return

        channel_id = message.text.strip()
        try:
            chat = bot.get_chat(channel_id)
            
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO channels (channel_id, channel_name, added_by, add_date) VALUES (?, ?, ?, ?)",
                (channel_id, chat.title, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            conn.commit()
            conn.close()
            
            bot.send_message(
                message.chat.id,
                f"✅ Kanal qo'shildi: {chat.title} ({channel_id})"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato: {str(e)}\nKanal qo'shilmadi. Iltimos, to'g'ri kanal username yoki ID sini kiriting."
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
            "Olib tashlamoqchi bo'lgan kanalni tanlang:",
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_channel_'))
    def handle_remove_channel_callback(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        channel_id = call.data.split('remove_channel_')[-1]  # Ensure correct parsing of channel_id

        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        try:
            # Fetch the channel name for confirmation
            cursor.execute("SELECT channel_name FROM channels WHERE channel_id=?", (channel_id,))
            result = cursor.fetchone()
            if not result:
                bot.answer_callback_query(call.id, "❌ Kanal topilmadi!")
                return

            channel_name = result[0]

            # Delete the channel and related subscriptions
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
            response = "📋 *Majburiy kanallar ro'yxati:*\n\n"
            for i, (channel_id, channel_name) in enumerate(channels, 1):
                response += f"{i}. {channel_name} ({channel_id})\n"
            response = validate_markdown(response)  # Validate and escape Markdown
            bot.send_message(message.chat.id, response, parse_mode="Markdown")
        except ApiTelegramException as e:
            error_message = f"Failed to send message: {e.description}"
            bot.send_message(message.chat.id, error_message)
            # Optionally log the error or notify the admin
            print(error_message)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_pay_', 'reject_pay_')))
    def handle_payment_decision(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        req_id = call.data.split('_')[-1]
        conn = None
        try:
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            cursor.execute("SELECT user_id, amount FROM payments WHERE id=?", (req_id,))
            result = cursor.fetchone()

            if not result:
                bot.answer_callback_query(call.id, "❌ So'rov topilmadi!")
                return

            user_id, amount = result

            if call.data.startswith('confirm_pay_'):
                cursor.execute("UPDATE payments SET status='completed' WHERE id=?", (req_id,))
                
                # Foydalanuvchi ma'lumotlarini olish
                cursor.execute("SELECT username, full_name FROM users WHERE user_id=?", (user_id,))
                user_data = cursor.fetchone()
                username = user_data[0] if user_data else "Noma'lum"
                full_name = user_data[1] if user_data else "Noma'lum"
                
                # Adminga isbot xabari yuborish
                proof_message = (
                    f"✅ To'lov tasdiqlandi\n\n"
                    f"👤 Foydalanuvchi: @{username}\n"
                    f"📝 Ism: {full_name}\n"
                    f"🆔 ID: {user_id}\n"
                    f"💰 Miqdor: {format_money(amount)}\n"
                    f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                try:
                    bot.send_message(admin_id, proof_message)
                except Exception as e:
                    print(f"Admin xabari yuborish xatosi: {e}")
                
                bot.answer_callback_query(call.id, "✅ To'lov tasdiqlandi!")
                bot.send_message(
                    user_id,
                    f"✅ {format_money(amount)} miqdordagi to'lovingiz tasdiqlandi!\n"
                    "Pul 10 daqiqa ichida kartangizga tushadi."
                )
                new_status = "✅ Tasdiqlangan"
            else:
                cursor.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
                cursor.execute("UPDATE payments SET status='rejected' WHERE id=?", (req_id,))
                bot.answer_callback_query(call.id, "❌ To'lov rad etildi!")
                bot.send_message(
                    user_id,
                    f"❌ {format_money(amount)} miqdordagi to'lov so'rovingiz rad etildi.\n"
                    f"💰 {format_money(amount)} miqdor hisobingizga qaytarildi."
                )
                new_status = "❌ Rad etilgan"

            conn.commit()

            # Check if the message content or reply markup has changed
            updated_text = f"{call.message.text}\n\n🔹 Status: {new_status}"
            if call.message.text != updated_text:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=updated_text,
                    reply_markup=None
                )

        except Exception as e:
            if conn:
                conn.rollback()
            bot.answer_callback_query(call.id, f"❌ Xato: {str(e)}")
            print(f"Payment decision error: {e}")
        finally:
            if conn:
                conn.close()

    @bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu" and m.from_user.id == admin_id)
    def back_to_main_menu(message):
        try:
            user_id = message.from_user.id
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance, spins_left FROM users WHERE user_id=?", (user_id,))
            user_data = cursor.fetchone()
            conn.close()
            
            if not user_data:
                balance = 0
                spins_left = 0
            else:
                balance, spins_left = user_data
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row(types.KeyboardButton("💵 Pul ishlash"))
            keyboard.row(types.KeyboardButton("📊 Hisobim"), types.KeyboardButton("👥 Do'stlarni taklif qilish"))

            if user_id == ADMIN_ID:
                keyboard.row(types.KeyboardButton("👑 Admin"))

            bot.send_message(
                message.chat.id,
                f"🎰 *Pul Yutish Boti Asosiy Menu!*\n\n"
                f"💵 Balans: {format_money(balance)}\n"
                f"🎡 Aylantirishlar: {spins_left}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Xato yuz berdi: {e}")
            bot.send_message(message.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

    @bot.message_handler(func=lambda m: m.text == "👑 Admin" and m.from_user.id == admin_id)
    def handle_admin_menu(message):
        handle_admin(message)

    @bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar" and m.from_user.id == admin_id)
    def handle_settings_menu(message):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(
            types.KeyboardButton("👥 Foydalanuvchilar"),
            types.KeyboardButton("📥 Download .db")
        )
        keyboard.row(
            types.KeyboardButton("📢 Xabar yuborish"),
            types.KeyboardButton("🚫 Foydalanuvchini bloklash")
        )
        keyboard.row(types.KeyboardButton("🔙 Qaytish"))
        bot.send_message(
            message.chat.id,
            "⚙️ *Sozlamalar menyusi*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish" and m.from_user.id == admin_id)
    def handle_broadcast_message(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_broadcast_message)

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
    def handle_cancel_broadcast(call):
        if call.from_user.id == admin_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📢 Xabar yuborish bekor qilindi.",
                reply_markup=None
            )
            # Clear the next step handler to prevent further processing
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

    def process_broadcast_message(message):
        broadcast_text = message.text
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Fetch all user IDs
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        success_count = 0
        failure_count = 0

        for (user_id,) in users:
            try:
                bot.send_message(user_id, broadcast_text)
                success_count += 1
            except Exception as e:
                print(f"Failed to send message to {user_id}: {e}")
                failure_count += 1

        bot.send_message(
            message.chat.id,
            f"✅ Xabar muvaffaqiyatli yuborildi: {success_count} ta foydalanuvchiga.\n"
            f"❌ Xabar yuborilmadi: {failure_count} ta foydalanuvchiga."
        )

    def escape_markdown(text):
        """Escape special characters for Markdown."""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text

    @bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar" and m.from_user.id == admin_id)
    def handle_users_list(message, page=1, sort_by="recent"):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Get total user count
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Pagination logic
        users_per_page = 5
        offset = (page - 1) * users_per_page
        total_pages = (total_users + users_per_page - 1) // users_per_page

        # Determine sort order
        if sort_by == "earned":
            order_by = "ORDER BY (SELECT SUM(amount) FROM prizes WHERE user_id = u.user_id) DESC"
        elif sort_by == "withdrawn":
            order_by = "ORDER BY (SELECT SUM(amount) FROM payments WHERE user_id = u.user_id AND status = 'completed') DESC"
        else:  # recent
            order_by = "ORDER BY u.created_at DESC"

        # Fetch users for the current page
        query = f"""
            SELECT 
                u.user_id, 
                u.full_name, 
                u.username, 
                u.phone_number, 
                u.balance, 
                u.created_at,
                (SELECT COUNT(*) FROM referals WHERE referer_id = u.user_id) AS referral_count,
                (SELECT SUM(amount) FROM payments WHERE user_id = u.user_id AND status = 'completed') AS total_withdrawn,
                (SELECT ru.full_name FROM referals r JOIN users ru ON r.referer_id = ru.user_id WHERE r.referee_id = u.user_id LIMIT 1) AS referred_by
            FROM users u
            {order_by}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, (users_per_page, offset))
        users = cursor.fetchall()
        conn.close()

        if not users:
            bot.send_message(message.chat.id, "❌ Foydalanuvchilar ro'yxati bo'sh.")
            return

        response = f"👥 *Foydalanuvchilar ro'yxati (Sahifa {page}/{total_pages}):*\n\n"
        for user_id, full_name, username, phone_number, balance, created_at, referral_count, total_withdrawn, referred_by in users:
            referred_by_text = f"🔗 Kim orqali: {referred_by}" if referred_by else "🔗 Kim orqali: To'g'ridan-to'g'ri"
            response += (
                f"🆔 ID: {user_id}\n"
                f"👤 Ismi: {escape_markdown(full_name or 'Unknown')}\n"
                f"📛 Username: @{escape_markdown(username or 'Unknown')}\n"
                f"📱 Telefon: {escape_markdown(phone_number or 'Unknown')}\n"
                f"💰 Balans: {format_money(balance)}\n"
                f"🤝 Referallar: {referral_count}\n"
                f"💸 Yechib olingan: {format_money(total_withdrawn or 0)}\n"
                f"📅 Qo'shilgan: {created_at or 'Unknown'}\n"
                f"{referred_by_text}\n\n"
            )

        # Inline keyboard for filters, pagination and Excel download
        keyboard = types.InlineKeyboardMarkup()
        
        # Filter buttons
        filter_row = []
        filter_row.append(types.InlineKeyboardButton("📅 Oxirgi", callback_data=f"users_filter_recent_{page}"))
        filter_row.append(types.InlineKeyboardButton("💰 Ko'p pul", callback_data=f"users_filter_earned_{page}"))
        filter_row.append(types.InlineKeyboardButton("💸 Yechib olingan", callback_data=f"users_filter_withdrawn_{page}"))
        keyboard.row(*filter_row)
        
        # Pagination buttons
        row = []
        if page > 1:
            row.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"users_page_{page - 1}_{sort_by}"))
        if page < total_pages:
            row.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"users_page_{page + 1}_{sort_by}"))
        if row:
            keyboard.row(*row)
        keyboard.add(types.InlineKeyboardButton("📥 Excel ro'yxat", callback_data="download_users_excel"))

        bot.send_message(message.chat.id, response, parse_mode="Markdown", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("users_filter_"))
    def handle_users_filter(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        parts = call.data.split('_')
        filter_type = parts[2]  # recent, earned, withdrawn
        page = int(parts[3]) if len(parts) > 3 else 1
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        handle_users_list(call.message, page, filter_type)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("users_page_"))
    def handle_users_pagination(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        # Extract the page number and sort_by from the callback data
        parts = call.data.split('_')
        page = int(parts[2])
        sort_by = parts[3] if len(parts) > 3 else "recent"
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        handle_users_list(call.message, page, sort_by)

    @bot.callback_query_handler(func=lambda call: call.data == "download_users_excel")
    def handle_download_users_excel(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                u.user_id, 
                u.full_name, 
                u.username, 
                u.phone_number, 
                u.balance,
                u.created_at,
                (SELECT COUNT(*) FROM referals WHERE referer_id = u.user_id) AS referral_count,
                (SELECT SUM(amount) FROM payments WHERE user_id = u.user_id AND status = 'completed') AS total_withdrawn,
                (SELECT ru.full_name FROM referals r JOIN users ru ON r.referer_id = ru.user_id WHERE r.referee_id = u.user_id LIMIT 1) AS referred_by
            FROM users u
        """)
        users = cursor.fetchall()
        conn.close()

        if not users:
            bot.answer_callback_query(call.id, "❌ Foydalanuvchilar ro'yxati bo'sh!")
            return

        # Create Excel file
        excel_path = "all_users.xlsx"
        workbook = xlsxwriter.Workbook(excel_path)
        worksheet = workbook.add_worksheet()
        worksheet.write_row(0, 0, ["ID", "Full Name", "Username", "Phone Number", "Balance", "Created At", "Referrals Count", "Total Withdrawn", "Referred By"])
        for row_num, (user_id, full_name, username, phone_number, balance, created_at, referral_count, total_withdrawn, referred_by) in enumerate(users, start=1):
            referred_by_name = referred_by or "To'g'ridan-to'g'ri"
            worksheet.write_row(row_num, 0, [
                user_id,
                full_name or "none",
                username or "none",
                phone_number or "none",
                balance,
                created_at or "none",
                referral_count or 0,
                total_withdrawn or 0,
                referred_by_name
            ])
        workbook.close()

        # Send Excel file
        with open(excel_path, 'rb') as excel_file:
            bot.send_document(call.message.chat.id, excel_file)

        bot.answer_callback_query(call.id, "📥 Excel fayl tayyor!")

    @bot.message_handler(func=lambda m: m.text == "🔄 Hisobni 0 qilish" and m.from_user.id == admin_id)
    def handle_reset_user_balance(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_reset_input")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "❗ Foydalanuvchi ID sini yuboring:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_reset_user_balance)

    def process_reset_user_balance(message):
        try:
            # Check if cancel button was clicked
            if message.text and message.text.startswith('/'):
                return
            
            user_id = int(message.text.strip())
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Check if the user exists
            cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (user_id,))
            user = cursor.fetchone()

            if not user:
                bot.send_message(
                    message.chat.id,
                    f"❌ Foydalanuvchi ID: {user_id} topilmadi."
                )
                conn.close()
                return

            full_name, current_balance = user
            
            # Inline tugmalar tasdiqlash uchun
            keyboard = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_reset_{user_id}")
            btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_reset")
            keyboard.add(btn_confirm, btn_cancel)
            
            bot.send_message(
                message.chat.id,
                f"⚠️ *Hisobni 0 qilish tasdiqlash:*\n\n"
                f"👤 Foydalanuvchi: {full_name}\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Joriy balans: {format_money(current_balance)}\n"
                f"🔄 Yangi balans: 0 so'm\n\n"
                f"❗ Bu amalni bekor qilib bo'lmaydi!",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            conn.close()
            
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Noto'g'ri ID formati. Iltimos, faqat raqam kiriting."
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato yuz berdi: {str(e)}"
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_reset_'))
    def handle_confirm_reset(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return
        
        try:
            user_id = int(call.data.split('_')[-1])
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            # Reset user balance to 0
            cursor.execute(
                "UPDATE users SET balance=0 WHERE user_id=?",
                (user_id,)
            )
            conn.commit()
            conn.close()
            
            # Send notification to user
            bot.send_message(
                user_id,
                f"⚠️ *Hisobingiz qayta tiklandi*\n\n"
                f"💰 Balans: 0 so'm"
            )
            
            # Notify admin
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Foydalanuvchi ID: {user_id} ning hisobi 0 qilinidi!",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "✅ Balans 0 qilinidi!")
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Xato: {str(e)}")
            print(f"Reset balance error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_reset_input")
    def handle_cancel_reset_input(call):
        if call.from_user.id == admin_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Hisobni 0 qilish bekor qilindi.",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "Bekor qilindi!")
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_reset")
    def handle_cancel_reset(call):
        if call.from_user.id == admin_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Hisobni 0 qilish bekor qilindi.",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "Bekor qilindi!")
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

    @bot.message_handler(func=lambda m: m.text == "🎁 Bonus berish" and m.from_user.id == admin_id)
    def handle_give_bonus(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_bonus_input")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "🎁 Bonus berish uchun quyidagi formatda ma'lumotlarni yuboring:\n\n"
            "123456789\n"
            "5\n\n"
            "1-qator: Foydalanuvchi ID\n"
            "2-qator: Bermoqchi bo'lgan aylantirish soni",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_give_bonus)

    def process_give_bonus(message):
        try:
            # Ma'lumotlarni ajratib olish
            data = message.text.split('\n')
            if len(data) < 2:
                raise ValueError("Ma'lumotlar to'liq kiritilmagan")
            
            user_id = int(data[0].strip())
            spins = int(data[1].strip())
            
            if spins <= 0:
                raise ValueError("Aylantirish soni 0 dan katta bo'lishi kerak")

            # Foydalanuvchi mavjudligini tekshirish
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT full_name, spins_left FROM users WHERE user_id=?", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                bot.send_message(
                    message.chat.id,
                    f"❌ Foydalanuvchi ID: {user_id} topilmadi."
                )
                conn.close()
                return
            
            full_name, current_spins = result
            
            # Inline tugmalar
            keyboard = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_bonus_{user_id}_{spins}")
            btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_bonus")
            keyboard.add(btn_confirm, btn_cancel)
            
            bot.send_message(
                message.chat.id,
                f"🎁 *Bonus berish tasdiqlash:*\n\n"
                f"👤 Foydalanuvchi: {full_name}\n"
                f"🆔 ID: {user_id}\n"
                f"🎡 Joriy aylantirish: {current_spins}\n"
                f"➕ Bermoqchi bo'lgan bonus: {spins}\n"
                f"📊 Jami bo'ladi: {current_spins + spins}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            conn.close()
            
        except ValueError as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato: {str(e)}\n\n"
                "Iltimos, ma'lumotlarni quyidagi formatda qayta yuboring:\n\n"
                "123456789\n"
                "5\n\n"
                "1-qator: Foydalanuvchi ID (faqat raqamlar)\n"
                "2-qator: Aylantirish soni (faqat raqamlar)"
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xato yuz berdi: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_bonus_'))
    def handle_confirm_bonus(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return
        
        try:
            # callback_data dan user_id va spins ni olish
            parts = call.data.split('_')
            user_id = int(parts[2])
            spins = int(parts[3])
            
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            # Foydalanuvchiga aylantirish qo'shish
            cursor.execute(
                "UPDATE users SET spins_left=spins_left+? WHERE user_id=?",
                (spins, user_id)
            )
            conn.commit()
            
            # Foydalanuvchiga xabar yuborish
            bot.send_message(
                user_id,
                f"🎁 *Siz bonus oldingiz!*\n\n"
                f"➕ {spins} ta aylantirish imkoniyati qo'shildi!\n"
                f"💎 Bonusdan foydalaning va pul ishlashda davom eting!",
                parse_mode="Markdown"
            )
            
            conn.close()
            
            # Adminni xabardor qilish
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Foydalanuvchi ID: {user_id} ga {spins} ta aylantirish bonus berildi!\n"
                     f"📨 Foydalanuvchiga xabar yuborildi.",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "✅ Bonus muvaffaqiyatli berildi!")
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Xato: {str(e)}")
            print(f"Bonus confirmation error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_bonus_input")
    def handle_cancel_bonus_input(call):
        if call.from_user.id == admin_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Bonus berish bekor qilindi.",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "Bekor qilindi!")
            # Next step handler ni to'xtatish
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_bonus")
    def handle_cancel_bonus(call):
        if call.from_user.id == admin_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Bonus berish bekor qilindi.",
                reply_markup=None
            )
            bot.answer_callback_query(call.id, "Bekor qilindi!")
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

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