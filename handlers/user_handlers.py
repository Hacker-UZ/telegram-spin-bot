from telebot import types
from datetime import datetime
import sqlite3
from config import INITIAL_SPINS, MIN_WITHDRAWAL, ADMIN_ID, PRIZES_LOW_BALANCE, PRIZES_HIGH_BALANCE, REFERAL_SPINS
import random

def setup_user_handlers(bot):
    def check_subscription(bot, user_id):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Fetch all mandatory channels
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        channels = cursor.fetchall()

        if not channels:
            conn.close()
            return True  # No channels to check

        unsubscribed = []
        for channel_id, channel_name in channels:
            try:
                member = bot.get_chat_member(channel_id, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    unsubscribed.append((channel_id, channel_name))
            except Exception as e:
                print(f"Error checking subscription for channel {channel_id}: {e}")
                continue  # Skip this channel and proceed with others

        if unsubscribed:
            conn.close()
            return False  # User is not subscribed to all channels

        conn.close()
        return True  # User is subscribed to all channels

    def referral_logic(bot, message, user_id):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        if len(message.text.split()) > 1:
            referal_code = message.text.split()[1]
            if referal_code.startswith('ref'):
                referer_id = int(referal_code[3:])
                if referer_id != user_id:  # Prevent self-referral
                    # Check if the referral already exists
                    cursor.execute(
                        "SELECT COUNT(*) FROM referals WHERE referee_id=?", (user_id,)
                    )
                    referral_exists = cursor.fetchone()[0] > 0

                    if not referral_exists:
                        # Temporarily store the referral
                        cursor.execute(
                            "INSERT INTO referals (referer_id, referee_id, date, bonus_given) VALUES (?, ?, ?, ?)",
                            (referer_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0)
                        )
                        conn.commit()

                        # Notify the referred user
                        bot.send_message(
                            user_id,
                            "✅ Sizning referal kodingiz qabul qilindi.\n"
                            "📢 Kanallarga obuna bo'ling va bonuslaringiz hisobingizga qo'shiladi!"
                        )

                        # Notify the referral owner
                        cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
                        referred_user_name = cursor.fetchone()[0] or "Noma'lum"
                        bot.send_message(
                            referer_id,
                            f"🎉 Sizning referalingiz {referred_user_name} ro'yxatdan o'tdi!\n"
                            "📢 U kanallarga obuna bo'lgandan so'ng, bonuslaringiz hisobingizga qo'shiladi.",
                            parse_mode="Markdown"
                        )
        conn.close()

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        try:
            user_id = message.from_user.id

            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Check if the user exists
            cursor.execute("SELECT spins_left FROM users WHERE user_id=?", (user_id,))
            user = cursor.fetchone()

            if not user:
                # Add new user or reinitialize blocked user with initial spins
                cursor.execute(
                    """INSERT OR REPLACE INTO users 
                       (user_id, username, full_name, spins_left, balance, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, message.from_user.username or "", 
                     message.from_user.full_name or "", INITIAL_SPINS, 0,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()

                # Process referral logic for new users
                referral_logic(bot, message, user_id)

            # Check subscription status
            if not check_subscription(bot, user_id):
                prompt_subscription(bot, message)
                return

            # Check if the user has a referral and process bonuses
            cursor.execute(
                "SELECT referer_id, bonus_given FROM referals WHERE referee_id=? AND referer_id IS NOT NULL", (user_id,)
            )
            referal_data = cursor.fetchone()
            if referal_data:
                referer_id, bonus_given = referal_data

                if not bonus_given:  # Only give the bonus if it hasn't been given yet
                    # Add bonuses to the referral owner
                    cursor.execute(
                        "UPDATE users SET spins_left=spins_left+? WHERE user_id=?",
                        (REFERAL_SPINS, referer_id)
                    )
                    # Mark the bonus as given
                    cursor.execute(
                        "UPDATE referals SET bonus_given=1 WHERE referee_id=? AND referer_id=?", (user_id, referer_id)
                    )
                    conn.commit()

                    # Notify the referral owner
                    cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
                    referred_user_name = cursor.fetchone()[0] or "Noma'lum"
                    bot.send_message(
                        referer_id,
                        f"🎉 Sizning referalingiz {referred_user_name} kanallarga obuna bo'ldi!\n"
                        f"Sizga *{REFERAL_SPINS}* aylantirish imkoniyati berildi!",
                        parse_mode="Markdown"
                    )

            # Transition to the main menu
            show_main_menu(message)
        except Exception as e:
            print(f"Error in /start command: {e}")
            bot.send_message(message.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")
        finally:
            if 'conn' in locals():
                conn.close()

    def prompt_subscription(bot, message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Fetch all mandatory channels
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        channels = cursor.fetchall()
        conn.close()

        keyboard = types.InlineKeyboardMarkup()
        for channel_id, channel_name in channels:
            try:
                member = bot.get_chat_member(channel_id, message.from_user.id)
                status_icon = "✅" if member.status in ['member', 'administrator', 'creator'] else "❌"
            except Exception:
                status_icon = "❌"  # Default to not subscribed if an error occurs

            keyboard.add(types.InlineKeyboardButton(
                text=f"{status_icon} {channel_name}",
                url=f"https://t.me/{channel_id[1:] if channel_id.startswith('@') else channel_id}"
            ))

        bot.send_message(
            message.chat.id,
            "📢 Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling.\n"
            "✅ Obuna bo'lgandan so'ng, /start buyrug'ini bosing.",
            reply_markup=keyboard
        )

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        if message.contact:
            user_id = message.from_user.id
            phone_number = message.contact.phone_number

            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            try:
                # Save the phone number to the database
                cursor.execute("UPDATE users SET phone_number=? WHERE user_id=?", (phone_number, user_id))
                conn.commit()

                # Notify the user
                bot.send_message(message.chat.id, "✅ Telefon raqamingiz saqlandi!")

                # Check subscription status
                if not check_subscription(bot, user_id):
                    prompt_subscription(bot, message)
                    return

                # Transition to the main menu
                show_main_menu(message)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Telefon raqamini saqlashda xatolik yuz berdi: {str(e)}")
            finally:
                conn.close()

    def show_main_menu(message):
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

            # Add "Admin" button if the user is an admin
            if user_id == ADMIN_ID:
                keyboard.row(types.KeyboardButton("👑 Admin"))

            bot.send_message(
                message.chat.id,
                f"🎰 *Pul Yutish Botiga xush kelibsiz!*\n\n"
                f"💵 Balans: {balance:,} so'm\n"
                f"🎡 Aylantirishlar: {spins_left}\n\n",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error in show_main_menu: {e}")
            bot.send_message(message.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

    @bot.message_handler(func=lambda m: m.text == "💵 Pul ishlash")
    def handle_spin_request(message):
        try:
            # Check subscription first
            if not check_subscription(bot, message.from_user.id):
                prompt_subscription(bot, message)
                return

            # Send baraban emoji with an inline button
            keyboard = types.InlineKeyboardMarkup()
            spin_button = types.InlineKeyboardButton("🎡 Aylantirish", callback_data="spin")
            keyboard.add(spin_button)

            bot.send_message(
                message.chat.id,
                "🎰 Baraban aylantirishga tayyor!",
                reply_markup=keyboard
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xato yuz berdi: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data == "spin")
    def handle_spin(call):
        try:
            user_id = call.from_user.id
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Fetch user spins and balance
            cursor.execute("SELECT spins_left, balance FROM users WHERE user_id=?", (user_id,))
            result = cursor.fetchone()

            if not result:
                bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!")
                return

            spins_left, balance = result

            if spins_left <= 0:
                bot.answer_callback_query(call.id, "❌ Sizda aylantirish imkoniyati qolmadi!")
                bot.send_message(call.message.chat.id,
                    "❌ Sizda aylantirish imkoniyati qolmadi!\n\n"
                    "👥 Do'stlaringizni taklif qilib, yana 1ta aylantirish imkoniyatini oling!\n",
                    parse_mode="Markdown"
                )
                return

            # Remove the inline button
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

            # Wait for 2 seconds before showing the prize
            bot.answer_callback_query(call.id, "🎡 Aylantirilyapti...")
            import time
            time.sleep(1.2)

            # Balansga qarab yutuqlarni tanlash
            if balance >= 18000:
                prize = random.choice(PRIZES_HIGH_BALANCE)
            else:
                prize = random.choice(PRIZES_LOW_BALANCE)
            
            new_balance = balance + prize
            new_spins = spins_left - 1

            # Update the database
            cursor.execute(
                "UPDATE users SET balance=?, spins_left=? WHERE user_id=?",
                (new_balance, new_spins, user_id)
            )
            cursor.execute(
                "INSERT INTO prizes (user_id, amount, date) VALUES (?, ?, ?)",
                (user_id, prize, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()

            # Send the prize message
            if prize == 0:
                bot.send_message(
                    call.message.chat.id,
                    f"😔 Afsuski, siz bu safar yutmadingiz!\n\n"
                    f"💵 Balans: {new_balance:,} so'm\n"
                    f"🎡 Qolgan aylantirishlar: {new_spins}",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"🎉 Tabriklaymiz! Siz yutdingiz: *{prize:,} so'm*!\n\n"
                    f"💵 Yangi balans: {new_balance:,} so'm\n"
                    f"🎡 Qolgan aylantirishlar: {new_spins}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Xato yuz berdi: {str(e)}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: m.text == "📊 Hisobim")
    def handle_account_info(message):
        try:
            if not check_subscription(bot, message.from_user.id):
                prompt_subscription(bot, message)
                return
            user_id = message.from_user.id
            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Fetch user data
            cursor.execute("SELECT balance, spins_left FROM users WHERE user_id=?", (user_id,))
            user_data = cursor.fetchone()

            # Fetch referral count
            cursor.execute("SELECT COUNT(*) FROM referals WHERE referer_id=?", (user_id,))
            referral_count = cursor.fetchone()[0]

            conn.close()

            if not user_data:
                balance = 0
                spins_left = 0
            else:
                balance, spins_left = user_data

            # Prepare the account information message
            account_info = (
                f"📊 *Sizning hisobingiz:*\n\n"
                f"🆔 ID raqamingiz: {user_id}\n"
                f"💵 Balans: {balance:,} so'm\n"
                f"🎡 Aylantirish imkoniyati: {spins_left}\n"
                f"👥 Referallar soni: {referral_count}\n\n"
                f"🎯 Minimal pul yechish: {MIN_WITHDRAWAL} so'm"
            )

             # Add an inline button for withdrawal
            keyboard = types.InlineKeyboardMarkup()
            withdraw_button = types.InlineKeyboardButton(
                text="💸 Pul yechish", callback_data="withdraw"
            )
            keyboard.add(withdraw_button)

            # Send the account information
            bot.send_message(
                message.chat.id,
                account_info,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xato yuz berdi: {str(e)}")

    @bot.message_handler(func=lambda m: m.text == "👥 Do'stlarni taklif qilish")
    def handle_referal(message):
        try:
            # Check subscription first
            if not check_subscription(bot, message.from_user.id):
                prompt_subscription(bot, message)
                return
                
            user_id = message.from_user.id
            bot.send_message(
                message.chat.id,
                f"<b>💁‍♂ Yana bepul baraban aylantirishni istaysizmi?</b>\n\n"
                f"<b>👤 Har bir taklif qilingan do'stingiz 1️⃣ marotaba baraban aylantirish imkonini beradi.</b>\n\n",
                parse_mode="HTML"
            )
            
            bot_username = bot.get_me().username
            referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
            share_text = "📯 Baraban aylantirib pul ishlash vaqti keldi!\nHammasi 💯 foiz ishonchli"
            
            keyboard = types.InlineKeyboardMarkup()
            btn_share = types.InlineKeyboardButton(
                "📤 Do'stlarga yuborish", 
                url=f"https://t.me/share/url?text={share_text}&url={referral_link}\n"
            )
            keyboard.add(btn_share)
            
            bot.send_message(
                message.chat.id,
                f"<b>🔗 Sizning referalingiz:</b>\n\n"
                f"<code>{referral_link}</code>\n\n"
                f"<b>Ushbu linkni do'stlaringizga yuboring va bonus oling!</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error in handle_referal: {e}")
            bot.send_message(message.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

