from telebot import types
from datetime import datetime
import sqlite3
import xlsxwriter

def format_money(amount):
    return f"{amount:,} so'm"

def escape_markdown(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def setup_admin_users(bot_instance, admin_id):
    bot = bot_instance

    @bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar" and m.from_user.id == admin_id)
    def handle_users_list(message, page=1, sort_by="recent"):
        conn = sqlite3.connect('pul_yutish.db')
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        users_per_page = 5
        offset = (page - 1) * users_per_page
        total_pages = (total_users + users_per_page - 1) // users_per_page

        if sort_by == "earned":
            order_by = "ORDER BY (SELECT SUM(amount) FROM prizes WHERE user_id = u.user_id) DESC"
        elif sort_by == "withdrawn":
            order_by = "ORDER BY (SELECT SUM(amount) FROM payments WHERE user_id = u.user_id AND status = 'completed') DESC"
        else:
            order_by = "ORDER BY u.created_at DESC"

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

        keyboard = types.InlineKeyboardMarkup()
        
        filter_row = []
        filter_row.append(types.InlineKeyboardButton("📅 Oxirgi", callback_data=f"users_filter_recent_{page}"))
        filter_row.append(types.InlineKeyboardButton("💰 Ko'p pul", callback_data=f"users_filter_earned_{page}"))
        filter_row.append(types.InlineKeyboardButton("💸 Yechib olingan", callback_data=f"users_filter_withdrawn_{page}"))
        keyboard.row(*filter_row)
        
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
        filter_type = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 1
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        handle_users_list(call.message, page, filter_type)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("users_page_"))
    def handle_users_pagination(call):
        if call.from_user.id != admin_id:
            bot.answer_callback_query(call.id, "❌ Sizga ruxsat yo'q!")
            return

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
            bot.send_document(call.message.chat.id, excel_file)

        bot.answer_callback_query(call.id, "📥 Excel fayl tayyor!")
