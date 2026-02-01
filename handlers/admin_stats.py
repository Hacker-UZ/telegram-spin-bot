from telebot import types
from datetime import datetime
import sqlite3

def format_money(amount):
    return f"{amount:,} so'm"

def setup_admin_stats(bot_instance, admin_id):
    bot = bot_instance

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
        
        # Jami foydalanuvchilar balansi
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Inline tugmalar
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
            f"🎯 Jami yutqazilgan summa: {format_money(total_balance)}\n"
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
        
        filter_type = call.data.split('_')[1]
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        if filter_type == "daily":
            filter_text = "📅 *Kunlik foydalanuvchilar*"
            query = "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"
        elif filter_type == "weekly":
            filter_text = "📆 *Haftalik foydalanuvchilar*"
            query = "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')"
        else:
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
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
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
                 f"🎯 Jami yutqazilgan summa: {format_money(total_balance)}\n"
                 f"💰 Jami to'langan summa: {format_money(total_payout)}\n"
                 f"⏳ Ko'rib chiqilishi kerak bo'lgan to'lovlar: {pending_payments}\n\n"
                 f"👥 *Foydalanuvchilar ma'lumoti:*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
