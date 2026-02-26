from telebot import types
from datetime import datetime
import sqlite3
from config import INITIAL_SPINS, MIN_WITHDRAWAL, ADMIN_ID, PRIZES_LOW_BALANCE, PRIZES_HIGH_BALANCE, REFERAL_SPINS
from database import get_referal_by_referee
import random

def setup_user_handlers(bot_instance):
    bot = bot_instance
    
    def is_user_banned(user_id):
        """Foydalanuvchi ban qilinganligini tekshirish"""
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM blacklist WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    # Ban qilingan foydalanuvchilar uchun middleware
    @bot.message_handler(func=lambda m: is_user_banned(m.from_user.id))
    def block_banned_user_messages(message):
        bot.send_message(message.chat.id, "🚫 Bot hozir ish faoliyatida emas. Keyinroq qayta urinib ko'ring.")

    @bot.callback_query_handler(func=lambda call: is_user_banned(call.from_user.id))
    def block_banned_user_callbacks(call):
        bot.answer_callback_query(call.id, "🚫 Bot hozir ish faoliyatida emas.")

    def extract_channel_id(channel_link):
        """Link'dan channel_id ni ajratib olish"""
        if channel_link.startswith("@"):
            return channel_link
        elif "https://t.me/+" in channel_link:
            # Private kanal invite link
            return channel_link
        elif "https://t.me/" in channel_link:
            # https://t.me/channel_name -> @channel_name
            username = channel_link.replace("https://t.me/", "").split("?")[0].split("/")[0]
            return "@" + username
        elif "t.me/" in channel_link:
            # t.me/channel_name -> @channel_name
            username = channel_link.replace("t.me/", "").split("?")[0].split("/")[0]
            return "@" + username
        else:
            return "@" + channel_link
    
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
        subscribed = []
        
        for channel_id, channel_name in channels:
            try:
                # Private kanal invite link'larini tekshirvdan o'tkazish
                if channel_id.startswith("https://t.me/+"):
                    # Private kanal - tekshirish kerak emas, skip
                    continue
                
                # Query parametrli link'larni tekshirvdan o'tkazish (masalan, ?start=...)
                if "?" in channel_id:
                    # Query parametri bo'lgan link - tekshirish kerak emas, skip
                    continue
                
                # Channel_id'ni to'g'ri formatga aylantirib olish
                api_channel_id = extract_channel_id(channel_id)
                
                # Oddiy kanal tekshiruvi
                try:
                    member = bot.get_chat_member(api_channel_id, user_id)
                    if member.status not in ['member', 'administrator', 'creator']:
                        unsubscribed.append(channel_id)
                    else:
                        subscribed.append(channel_id)
                except:
                    # Agar tekshirish xatosi bo'lsa, subscribe qilinmagan deb hisob qil
                    unsubscribed.append(channel_id)
            except Exception as e:
                print(f"Error checking subscription for channel {channel_id}: {e}")
                unsubscribed.append(channel_id)

        conn.commit()
        conn.close()
        return len(unsubscribed) == 0

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
        if is_user_banned(message.from_user.id):
            bot.send_message(message.from_user.id, "🚫 Bot hozir ish faoliyatida emas. Keyinroq qayta urinib ko'ring.")
            return
        
        try:
            user_id = message.from_user.id

            conn = sqlite3.connect('pul_yutish.db')
            cursor = conn.cursor()

            # Check if the user exists
            cursor.execute("SELECT spins_left FROM users WHERE user_id=?", (user_id,))
            user = cursor.fetchone()

            if not user:
                # Add new user with initial spins
                cursor.execute(
                    """INSERT INTO users 
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
        user_id = message.from_user.id
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        # Fetch all mandatory channels
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        channels = cursor.fetchall()
        conn.close()

        if not channels:
            # Agar kanallar bo'lmasa, to'g'ridan-to'g'ri asosiy menyuni ko'rsatish
            show_main_menu(message)
            return

        # Faqat obuna bo'lmagan public kanallarni filter qilish
        unsubscribed_public_channels = []
        all_private_channels = []
        
        for channel_id, channel_name in channels:
            try:
                # Private kanal invite link'larini ajratib olish
                if channel_id.startswith("https://t.me/+"):
                    # Private kanal - private kanallar ro'yxatiga qo'shish
                    all_private_channels.append((channel_id, channel_name))
                    continue
                
                # Query parametrli link'larni private kanal sifatida qo'shish (masalan, ?start=...)
                if "?" in channel_id:
                    # Query parametri bo'lgan link - private kanal deb hisoblab, private kanallar ro'yxatiga qo'shish
                    all_private_channels.append((channel_id, channel_name))
                    continue
                
                # Channel_id'ni to'g'ri formatga aylantirib olish
                api_channel_id = extract_channel_id(channel_id)
                
                # Oddiy kanal tekshiruvi
                try:
                    member = bot.get_chat_member(api_channel_id, user_id)
                    if member.status not in ['member', 'administrator', 'creator']:
                        unsubscribed_public_channels.append((channel_id, channel_name))
                except:
                    # Agar tekshirish xatosi bo'lsa, subscribe qilinmagan deb hisob qil
                    unsubscribed_public_channels.append((channel_id, channel_name))
            except Exception as e:
                print(f"Error checking subscription for channel {channel_id}: {e}")
                unsubscribed_public_channels.append((channel_id, channel_name))

        # Agar barcha public kanallarga obuna bo'lgan bo'lsa
        if not unsubscribed_public_channels:
            show_main_menu(message)
            return

        keyboard = types.InlineKeyboardMarkup()
        
        # Agar public kanallarga obuna bo'lmagan bo'lsa, private kanallarni ham qo'shish
        channels_to_show = unsubscribed_public_channels[:]
        if unsubscribed_public_channels and all_private_channels:
            channels_to_show.extend(all_private_channels)
        
        # Faqat obuna bo'lmagan kanallarni 2 ustunda chiqarish
        for i in range(0, len(channels_to_show), 2):
            row = []
            
            # Birinchi kanal
            channel_id, channel_name = channels_to_show[i]
            if channel_id.startswith("https://t.me/+"):
                url = channel_id
            elif channel_id.startswith("@"):
                url = f"https://t.me/{channel_id[1:]}"
            elif channel_id.startswith("https://"):
                url = channel_id
            else:
                url = f"https://t.me/{channel_id}"
            
            row.append(types.InlineKeyboardButton(
                text="➕ Obuna bo'lish",
                url=url
            ))
            
            # Ikkinchi kanal (agar mavjud bo'lsa)
            if i + 1 < len(channels_to_show):
                channel_id, channel_name = channels_to_show[i + 1]
                if channel_id.startswith("https://t.me/+"):
                    url = channel_id
                elif channel_id.startswith("@"):
                    url = f"https://t.me/{channel_id[1:]}"
                elif channel_id.startswith("https://"):
                    url = channel_id
                else:
                    url = f"https://t.me/{channel_id}"
                
                row.append(types.InlineKeyboardButton(
                    text="➕ Obuna bo'lish",
                    url=url
                ))
            
            keyboard.row(*row)

        # Tasdiqla tugmasi
        keyboard.add(types.InlineKeyboardButton(
            text="✅ Tasdiqlash",
            callback_data="verify_subscription"
        ))

        message_text = f"⚠️Botdan foydalanish uchun kanallarga obuna bo'ling:\n"
        
        bot.send_message(
            message.chat.id,
            message_text,
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data == "verify_subscription")
    def handle_verify_subscription(call):
        try:
            user_id = call.from_user.id
            
            # Kanal obunasini tekshirish
            if check_subscription(bot, user_id):
                # Barcha kanallarga obuna bo'lgan
                bot.answer_callback_query(call.id, "✅ Tayyor", show_alert=False)
                
                conn = sqlite3.connect('pul_yutish.db')
                cursor = conn.cursor()
                
                # Foydalanuvchi mavjudligini tekshirish
                cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
                user_exists = cursor.fetchone() is not None
                
                # Agar yangi foydalanuvchi bo'lsa, initial spins bilan yangi record yaratish
                if not user_exists:
                    cursor.execute(
                        """INSERT INTO users 
                           (user_id, username, full_name, spins_left, balance, created_at) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, call.from_user.username or "", 
                         call.from_user.full_name or "", INITIAL_SPINS, 0,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    conn.commit()
                    
                    # Process referral logic for new users
                    if len(call.message.text.split()) > 1:
                        referal_code = call.message.text.split()[1]
                        if referal_code.startswith('ref'):
                            try:
                                referer_id = int(referal_code[3:])
                                if referer_id != user_id:
                                    cursor.execute(
                                        "SELECT COUNT(*) FROM referals WHERE referee_id=?", (user_id,)
                                    )
                                    referral_exists = cursor.fetchone()[0] > 0
                                    
                                    if not referral_exists:
                                        cursor.execute(
                                            "INSERT INTO referals (referer_id, referee_id, date, bonus_given) VALUES (?, ?, ?, ?)",
                                            (referer_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0)
                                        )
                                        conn.commit()
                            except:
                                pass
                
                # Referral bonus berish (faqat yangi foydalanuvchi emas, balki obuna bo'lgan har bir foydalanuvchi uchun)
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
                    
                    # YANGI XUSUSIYAT: Kanal obunasi uchun bonus (OLIB TASHLANDI)
                    # Faqat jarima qismi qoldi - unsubscribe bo'lganda
                
                conn.close()
                
                # Obuna xabarini o'chirish
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except:
                    pass
                
                # Botdan foydalanish mumkinligini bildirish
                bot.send_message(
                    call.message.chat.id,
                    "✅ Tayyor /start ni bosing"
                )
            else:
                # Hali obuna bo'lmagan kanallar bor
                bot.answer_callback_query(
                    call.id, 
                    "❌ Iltimos, barcha kanallarga obuna bo'ling va qayta urinib ko'ring!", 
                    show_alert=True
                )
        except Exception as e:
            print(f"Error in verify_subscription: {e}")
            bot.answer_callback_query(call.id, f"❌ Xato yuz berdi: {str(e)}", show_alert=True)

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

    def show_main_menu(message_or_call):
        try:
            # message yoki callback query bo'lishi mumkin
            if hasattr(message_or_call, 'chat'):
                # Bu message
                user_id = message_or_call.from_user.id
                chat_id = message_or_call.chat.id
            else:
                # Bu callback query
                user_id = message_or_call.from_user.id
                chat_id = message_or_call.message.chat.id
                
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
                chat_id,
                f"🎰 *Pul Yutish Botiga xush kelibsiz!*\n\n"
                f"💵 Balans: {balance:,} so'm\n"
                f"🎡 Aylantirishlar: {spins_left}\n\n",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error in show_main_menu: {e}")
            try:
                if hasattr(message_or_call, 'chat'):
                    chat_id = message_or_call.chat.id
                else:
                    chat_id = message_or_call.message.chat.id
                bot.send_message(chat_id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")
            except:
                pass

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
                "🎰 *Baraban aylantirishga tayyor!*\n\n",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Spin request error: {e}")
            bot.send_message(
                message.chat.id, 
                "❌ *Xato yuz berdi!*\n"
                "Iltimos, qayta urinib ko'ring yoki admin'ga murojaat qiling.",
                parse_mode="Markdown"
            )

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
                bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi!", show_alert=True)
                return

            spins_left, balance = result

            if spins_left <= 0:
                bot.answer_callback_query(call.id, "❌ Aylantirish imkoniyati qolmadi!", show_alert=True)
                bot.send_message(call.message.chat.id,
                    "❌ *Aylantirish imkoniyati qolmadi!*\n\n"
                    "👥 Do'stlaringizni taklif qilib, yana aylantirish imkoniyatini oling!\n\n"
                    "_Har bir taklif qilingan do'st = 1 aylantirish_",
                    parse_mode="Markdown"
                )
                return

            # Remove the inline button
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

            # Wait for 2 seconds before showing the prize
            bot.answer_callback_query(call.id, "🎡 Aylantirilyapti...", show_alert=False)
            import time
            time.sleep(1.2)

            # Balansga qarab yutuqlarni tanlash
            if balance >= 3000:
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
                    f"😔 *Afsuski, siz bu safar yutmadingiz!*\n\n"
                    f"💵 Balans: {new_balance:,} so'm\n"
                    f"🎡 Qolgan aylantirishlar: {new_spins}\n\n",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"🎉 *Tabriklaymiz! Siz yutdingiz!*\n\n"
                    f"💰 *{prize:,} so'm*\n\n"
                    f"💵 Yangi balans: {new_balance:,} so'm\n"
                    f"🎡 Qolgan aylantirishlar: {new_spins}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"Spin error: {e}")
            bot.send_message(call.message.chat.id, 
                f"❌ *Xato yuz berdi!*\n"
                f"_Xato: {str(e)}_",
                parse_mode="Markdown"
            )
        finally:
            if 'conn' in locals():
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
                f"📊 *Sizning hisobingiz*\n\n"
                f"🆔 ID: `{user_id}`\n"
                f"💵 Balans: *{balance:,} so'm*\n"
                f"🎡 Aylantirish: *{spins_left}*\n"
                f"👥 Referallar: *{referral_count}*\n\n"
                f"💳 Minimal yechish: {MIN_WITHDRAWAL:,} so'm"
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
            print(f"Account info error: {e}")
            bot.send_message(
                message.chat.id, 
                "❌ *Xato yuz berdi!*\n"
                "Iltimos, qayta urinib ko'ring.",
                parse_mode="Markdown"
            )

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
                f"<b>👤 Har bir taklif qilingan do'stingiz 1️⃣ marotaba baraban aylantirish imkonini beradi.</b>\n"
                f"<b>✈️ Referalingizni do'stlaringizga yuboring!</b>",
                parse_mode="HTML"
            )
            
            bot_username = bot.get_me().username
            referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
            
            bot.send_message(
                message.chat.id,
                f"<b>📯 Baraban aylantir pul ishla!!!\n💸Hammasi 💯% ishonchli</b>\n\n"
                f"<b>{referral_link}</b>\n\n",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error in handle_referal: {e}")
            bot.send_message(message.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

