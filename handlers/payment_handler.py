from telebot import types
from config import MIN_WITHDRAWAL, CURRENCY
from database import get_user, update_user
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

def format_money(amount):
    return f"{amount:,} so'm"

def setup_payment_handler(bot, admin_id):
    @bot.callback_query_handler(func=lambda call: call.data == "withdraw")
    def handle_withdraw(call):
        user_id = call.from_user.id
        
        # Subscription tekshirish
        if not check_subscription_and_apply_penalty(user_id):
            bot.answer_callback_query(call.id, "⚠️ Kanallar tekshirildi!")
            return
        
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance, phone_number FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            bot.send_message(call.message.chat.id, "❌ Foydalanuvchi topilmadi!")
            return
        
        balance, phone_number = result

        if balance < MIN_WITHDRAWAL:
            bot.send_message(
                call.message.chat.id,
                f"❌ Minimal pul yechish miqdori {format_money(MIN_WITHDRAWAL)}\n"
                f"Sizning balansingiz: {format_money(balance)}"
            )
            return

        # Agar telefon raqami yo'q bo'lsa, avval so'raymiz
        if not phone_number:
            request_phone_number(call.message)
            return

        # Telefon raqami bor bo'lsa, karta ma'lumotlarini so'raymiz
        proceed_to_payment_info(call.message, user_id, balance)

    def process_payment_info(message, user_id, amount):
        try:
            # Ma'lumotlarni ajratib olish
            data = message.text.split('\n')
            if len(data) < 2:
                raise ValueError("Ma'lumotlar to'liq kiritilmagan")
            
            card_number = data[0].strip()
            card_holder = data[1].strip()
            
            # Karta raqamini tekshirish
            if not card_number.isdigit() or len(card_number) < 12:
                raise ValueError("Noto'g'ri karta raqami formati")

            # Ma'lumotlarni bazaga saqlash
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()
            
            cursor.execute('''INSERT INTO payments 
                            (user_id, card_number, card_holder, amount, request_date)
                            VALUES (?, ?, ?, ?, ?)''',
                         (user_id, card_number, card_holder, amount, 
                          datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M:%S")))
            
            # Balansni yangilash
            cursor.execute("UPDATE users SET balance=0 WHERE user_id=?", (user_id,))
            
            conn.commit()
            conn.close()
            
            # Foydalanuvchiga xabar
            bot.send_message(
                message.chat.id,
                f"✅ {format_money(amount)} miqdordagi to'lov so'rovingiz qabul qilindi!\n"
                "Adminlarimiz 24 soat ichida to'lovni amalga oshiradilar.\n\n"
                f"💳 Karta raqami: {card_number[:4]} **** **** {card_number[-4:]}\n"
                f"👤 Karta egasi: {card_holder}"
            )
            
            # Adminlarga xabar
            notify_admin(user_id, card_number, card_holder, amount)
            
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato: \n\n"
                "Iltimos, ma'lumotlarni quyidagi formatda qayta yuboring:\n\n"
                "8600123456789012\n"
                "Ism Familya\n\n"
                "1-qator: Karta raqami\n"
                "2-qator: Karta egasining ismi"
            )

    def notify_admin(user_id, card_number, card_holder, amount):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        # Foydalanuvchi ma'lumotlari
        cursor.execute("SELECT username, full_name FROM users WHERE user_id=?", (user_id,))
        username, full_name = cursor.fetchone()
        
        cursor.execute("SELECT phone_number FROM users WHERE user_id=?", (user_id,))
        phone_number = cursor.fetchone()[0]
        conn.close()
        
        bot.send_message(
            admin_id,
            f"🆕 Yangi to'lov so'rovi:\n\n"
            f"👤 Foydalanuvchi: @{username} ({full_name})\n"
            f"📱 Telefon: {phone_number}\n"
            f"💰 Miqdor: {format_money(amount)}\n"
            f"💳 Karta raqami: {card_number}\n"
            f"👤 Karta egasi: {card_holder}\n\n"
            f"📅 Sana: {datetime.now(ZoneInfo('Asia/Tashkent')).strftime('%Y-%m-%d %H:%M')}"
        )

    def process_withdrawal_request(message):
        try:
            user_id = message.from_user.id
            card_number = message.text.strip()

            # Validate card number
            if not card_number.isdigit() or len(card_number) < 12:
                bot.send_message(
                    message.chat.id,
                    "❌ Noto'g'ri karta raqami formati. Iltimos, faqat raqamlarni kiriting (kamida 12 ta raqam)."
                )
                return

            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Fetch user balance
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            balance = cursor.fetchone()[0]

            if balance < MIN_WITHDRAWAL:
                bot.send_message(
                    message.chat.id,
                    f"❌ Minimal pul yechish miqdori {MIN_WITHDRAWAL:,} so'm.\n"
                    f"Sizning balansingiz: {balance:,} so'm."
                )
                conn.close()
                return

            # Insert withdrawal request into the database
            cursor.execute(
                """INSERT INTO payments (user_id, card_number, amount, request_date, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, card_number, balance, datetime.now(ZoneInfo('Asia/Tashkent')).strftime("%Y-%m-%d %H:%M:%S"), 'pending')
            )

            # Reset user balance
            cursor.execute("UPDATE users SET balance=0 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()

            # Notify the user
            bot.send_message(
                message.chat.id,
                f"✅ {balance:,} so'm miqdordagi to'lov so'rovingiz qabul qilindi!\n"
                "Adminlarimiz 24 soat ichida to'lovni amalga oshiradilar.\n\n"
                f"💳 Karta raqami: {card_number[:4]} **** **** {card_number[-4:]}"
            )

            # Notify the admin
            notify_admin(user_id, card_number, balance)
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Xato yuz berdi: {str(e)}\n"
                "Iltimos, qayta urinib ko'ring."
            )

    @bot.message_handler(func=lambda m: m.text == "💸 Pul yechish")
    def handle_withdrawal_request(message):
        user_id = message.from_user.id
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        try:
            # Check if the user has a phone number
            cursor.execute("SELECT phone_number FROM users WHERE user_id=?", (user_id,))
            phone_number = cursor.fetchone()[0]

            if not phone_number:
                # Request phone number if not provided
                request_phone_number(message)
                return

            # Proceed with withdrawal logic
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            balance = cursor.fetchone()[0]

            if balance < MIN_WITHDRAWAL:
                bot.send_message(
                    message.chat.id,
                    f"❌ Pul yechish uchun minimal balans: {MIN_WITHDRAWAL:,} so'm."
                )
                return

            msg = bot.send_message(
                message.chat.id,
                "💳 Pul yechish uchun kartangiz raqamini kiriting:"
            )
            bot.register_next_step_handler(msg, process_withdrawal_request)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xato yuz berdi: {str(e)}")
        finally:
            conn.close()

    def request_phone_number(message):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        button = types.KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)
        keyboard.add(button)
        bot.send_message(
            message.chat.id,
            "📱 Pul yechish uchun telefon raqamingizni yuboring.",
            reply_markup=keyboard
        )

    def proceed_to_payment_info(message, user_id, balance):
        msg = bot.send_message(
            message.chat.id,
            "💳 Pul yechish uchun quyidagi formatda ma'lumotlarni yuboring:\n\n"
            "8600123456789012\n"
            "Ism Familya\n\n"
            "1-qator: Karta raqami (faqat raqamlar)\n"
            "2-qator: Karta egasining ismi (lotin harflarida)"
        )
        bot.register_next_step_handler(msg, process_payment_info, user_id, balance)

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        if message.contact:
            user_id = message.from_user.id
            phone_number = message.contact.phone_number

            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            try:
                # Telefon raqamini bazaga saqlash
                cursor.execute("UPDATE users SET phone_number=? WHERE user_id=?", (phone_number, user_id))
                conn.commit()

                # Balansni olish
                cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
                balance = cursor.fetchone()[0]

                if balance < MIN_WITHDRAWAL:
                    bot.send_message(
                        message.chat.id,
                        f"❌ Pul yechish uchun minimal balans: {format_money(MIN_WITHDRAWAL)}\n"
                        f"Sizning balansingiz: {format_money(balance)}"
                    )
                    conn.close()
                    return

                # Muvaffaqiyatlik xabari
                bot.send_message(message.chat.id, "✅ Telefon raqamingiz saqlandi!")
                
                # Karta ma'lumotlarini so'ramiz
                proceed_to_payment_info(message, user_id, balance)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Telefon raqamini saqlashda xatolik yuz berdi: {str(e)}")
            finally:
                conn.close()
