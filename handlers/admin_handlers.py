from telebot import types
from datetime import datetime
import sqlite3
import telebot
import os
import threading
import time
from config import MIN_WITHDRAWAL, INITIAL_SPINS, REFERAL_SPINS, PRIZES, ADMIN_ID
from .admin_stats import setup_admin_stats
from .admin_channels import setup_admin_channels
from .admin_users import setup_admin_users

def format_money(amount):
    return f"{amount:,} so'm"

def setup_admin_handlers(bot_instance, admin_id):
    global bot
    bot = bot_instance
    
    # Submodules'larni setup qilish
    setup_admin_stats(bot, admin_id)
    setup_admin_channels(bot, admin_id)
    setup_admin_users(bot, admin_id)
    
    import threading
    import time
    
    def send_db_backup():
        """Har 10 daqiqada database faylini adminga yuborish"""
        while True:
            try:
                time.sleep(600)
                db_path = 'pul_yutish.db'
                if os.path.exists(db_path):
                    with open(db_path, 'rb') as db_file:
                        bot.send_document(admin_id, db_file, caption="📊 Avtomatik DB backup")
            except Exception as e:
                print(f"DB backup xatosi: {e}")
    
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

    @bot.message_handler(func=lambda m: m.text == "🔙 Qaytish" and m.from_user.id == admin_id)
    def handle_channels_back(message):
        handle_admin(message)

    @bot.message_handler(func=lambda m: m.text == "🔙 Orqaga" and m.from_user.id == admin_id)
    def handle_broadcast_back(message):
        handle_admin(message)



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
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("📝 Oddi xabar yuborish")
        btn2 = types.KeyboardButton("🖼️ Rasmli xabar yuborish")
        btn3 = types.KeyboardButton("↪️ Forward xabar yuborish")
        btn4 = types.KeyboardButton("🔙 Orqaga")
        keyboard.row(btn1)
        keyboard.row(btn2)
        keyboard.row(btn3)
        keyboard.row(btn4)
        
        bot.send_message(
            message.chat.id,
            "📢 Qaysi turdagi xabar yubormoksiz?",
            reply_markup=keyboard
        )


    @bot.message_handler(func=lambda m: m.text == "📝 Oddi xabar yuborish" and m.from_user.id == admin_id)
    def handle_text_broadcast(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "📝 Barcha foydalanuvchilarga yuboriladigan matnni kiriting:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_text_broadcast)

    def process_text_broadcast(message):
        if message.text and message.text.startswith('/'):
            return
        
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
            f"✅ Matn muvaffaqiyatli yuborildi: {success_count} ta foydalanuvchiga.\n"
            f"❌ Xabar yuborilmadi: {failure_count} ta foydalanuvchiga."
        )

    @bot.message_handler(func=lambda m: m.text == "🖼️ Rasmli xabar yuborish" and m.from_user.id == admin_id)
    def handle_photo_broadcast(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "🖼️ Iltimos, rasm yuboring (Caption qo'shish ixtiyoriy):",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_photo_broadcast)

    def process_photo_broadcast(message):
        if not message.photo:
            bot.send_message(
                message.chat.id,
                "❌ Iltimos, rasm yuboring!"
            )
            return
        
        # Rasm ID va caption'ni olish
        photo_file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else None
        
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
                bot.send_photo(user_id, photo_file_id, caption=caption)
                success_count += 1
            except Exception as e:
                print(f"Failed to send photo to {user_id}: {e}")
                failure_count += 1

        bot.send_message(
            message.chat.id,
            f"✅ Rasm muvaffaqiyatli yuborildi: {success_count} ta foydalanuvchiga.\n"
            f"❌ Rasm yuborilmadi: {failure_count} ta foydalanuvchiga."
        )

    @bot.message_handler(func=lambda m: m.text == "↪️ Forward xabar yuborish" and m.from_user.id == admin_id)
    def handle_forward_broadcast(message):
        keyboard = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")
        keyboard.add(btn_cancel)
        
        msg = bot.send_message(
            message.chat.id,
            "↪️ Iltimos, forward qiladigan xabarni yuboring:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, process_forward_broadcast)

    def process_forward_broadcast(message):
        # Oddiy forward - hammasi forward qilish (1 rasm, 5 rasm, text, hammasi)
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Barcha foydalanuvchilarni olish
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        success_count = 0
        failure_count = 0

        for (user_id,) in users:
            try:
                # Xabarni to'liq forward qilish
                bot.forward_message(user_id, message.chat.id, message.message_id)
                success_count += 1
            except Exception as e:
                print(f"Failed to forward message to {user_id}: {e}")
                failure_count += 1

        bot.send_message(
            message.chat.id,
            f"✅ Xabar muvaffaqiyatli jo'natildi: {success_count} ta foydalanuvchiga.\n"
            f"❌ Xabar yuborilmadi: {failure_count} ta foydalanuvchiga."
        )


    @bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
    def handle_cancel_broadcast(call):
        if call.from_user.id == admin_id:
            bot.answer_callback_query(call.id, "Bekor qilindi!")
            # Clear the next step handler to prevent further processing
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")

    def escape_markdown(text):
        """Escape special characters for Markdown."""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text



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