from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext as Context
from database.models import User

async def balance_command(update: Update, context: Context):
    user = update.effective_user
    
    from main import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        if db_user:
            balance = db_user.balance
            total_rentals = db_user.total_rentals
            total_spent = db_user.total_spent
        else:
            balance = 0
            total_rentals = 0
            total_spent = 0
    
    if update.callback_query:
        query = update.callback_query
        keyboard = [
            [InlineKeyboardButton("📥 Nạp tiền", callback_data='menu_deposit')],
            [InlineKeyboardButton("📱 Thuê số", callback_data='menu_rent')],
            [InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = f"""💰 **SỐ DƯ TÀI KHOẢN**

• **Số dư:** {balance:,}đ
• **Đã thuê:** {total_rentals} số
• **Tổng chi:** {total_spent:,}đ

🆔 ID: {user.id}
📝 Username: @{user.username or 'Không có'}"""
        await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        keyboard = [
            [InlineKeyboardButton("📥 Nạp tiền", callback_data='menu_deposit')],
            [InlineKeyboardButton("📱 Thuê số", callback_data='menu_rent')],
            [InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = f"""💰 **SỐ DƯ TÀI KHOẢN**

• **Số dư:** {balance:,}đ
• **Đã thuê:** {total_rentals} số
• **Tổng chi:** {total_spent:,}đ

🆔 ID: {user.id}
📝 Username: @{user.username or 'Không có'}"""
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
