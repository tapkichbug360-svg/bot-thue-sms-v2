from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext as Context
from database.models import User, db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def balance_command(update: Update, context: Context):
    """Xem số dư tài khoản - FIX LỖI MARKDOWN"""
    user = update.effective_user
    
    from main import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        
        if not db_user:
            text = "❌ KHÔNG TÌM THẤY TÀI KHOẢN\n\nVui lòng gửi /start để đăng ký."
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        balance = db_user.balance
        total_spent = db_user.total_spent
        total_rentals = db_user.total_rentals
        
        # SỬA ĐỊNH DẠNG - BỎ ** không cần thiết
        text = (
            f"💰 SỐ DƯ TÀI KHOẢN\n\n"
            f"• User ID: {user.id}\n"
            f"• Tên: {user.first_name}\n"
            f"• Username: @{user.username or 'N/A'}\n\n"
            f"💳 Số dư hiện tại: {balance:,}đ\n"
            f"📊 Đã thuê: {total_rentals} số\n"
            f"💸 Tổng chi: {total_spent:,}đ\n\n"
            f"🔄 Chọn thao tác:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📥 Nạp tiền", callback_data="menu_deposit")],
            [InlineKeyboardButton("📱 Thuê số", callback_data="menu_rent")],
            [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, 
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text, 
                reply_markup=reply_markup
            )