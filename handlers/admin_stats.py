from telebot import types
from datetime import datetime, timedelta
import sqlite3
import xlsxwriter

def format_money(amount):
    return f"{amount:,} so'm"

def setup_admin_stats(bot_instance, admin_id):
    bot = bot_instance

    @bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id == admin_id)
    def show_stats(message):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()
        
        # Umumiy statistika
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals")
        total_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed'")
        total_payout = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")
        pending_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM channels")
        total_channels = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        # Kunlik statistika
        cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')")
        daily_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals WHERE date >= datetime('now', '-1 day')")
        daily_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed' AND request_date >= datetime('now', '-1 day')")
        daily_payout = cursor.fetchone()[0] or 0
        
        # Haftalik statistika
        cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')")
        weekly_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals WHERE date >= datetime('now', '-7 days')")
        weekly_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed' AND request_date >= datetime('now', '-7 days')")
        weekly_payout = cursor.fetchone()[0] or 0
        
        # Oylik statistika
        cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-30 days')")
        monthly_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM referals WHERE date >= datetime('now', '-30 days')")
        monthly_referals = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status='completed' AND request_date >= datetime('now', '-30 days')")
        monthly_payout = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Barcha statistikani bitta xabarga qo'shish
        combined_message = (
            f"📊 *BOT STATISTIKASI*\n"
            f"━━━━━━━━\n"
            f"*📈 UMUMIY MA'LUMOTLAR*\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"🤝 Jami referallar: {total_referals}\n"
            f"📢 Jami kanallar: {total_channels}\n"
            f"🎯 Jami yutqazilgan summa: {format_money(total_balance)}\n"
            f"💰 Jami to'langan summa: {format_money(total_payout)}\n"
            f"⏳ Ko'rib chiqilishi kerak: {pending_payments}\n"
            f"━━━━━━━━\n"
            f"*📅 KUNLIK STATISTIKA*\n"
            f"👥 Yangi foydalanuvchilar: {daily_users}\n"
            f"🤝 Yangi referallar: {daily_referals}\n"
            f"💰 To'langan summa: {format_money(daily_payout)}\n"
            f"━━━━━━━━\n"
            f"*📆 HAFTALIK STATISTIKA*\n"
            f"👥 Yangi foydalanuvchilar: {weekly_users}\n"
            f"🤝 Yangi referallar: {weekly_referals}\n"
            f"💰 To'langan summa: {format_money(weekly_payout)}\n"
            f"━━━━━━━━\n"
            f"*📋 OYLIK STATISTIKA*\n"
            f"👥 Yangi foydalanuvchilar: {monthly_users}\n"
            f"🤝 Yangi referallar: {monthly_referals}\n"
            f"💰 To'langan summa: {format_money(monthly_payout)}\n"
        )
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("📥 Excel ro'yxat", callback_data="download_users_excel"))
        
        bot.send_message(
            message.chat.id,
            combined_message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "download_users_excel")
    def handle_download_users_excel(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

        try:
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

            with open(excel_path, 'rb') as excel_file:
                bot.send_document(call.message.chat.id, excel_file, caption="📥 Foydalanuvchilar ro'yxati")

            bot.answer_callback_query(call.id, "✅ Excel fayl yuborildi!")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Xato: {str(e)}")
            print(f"Excel download error: {e}")