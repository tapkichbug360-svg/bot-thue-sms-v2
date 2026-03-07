from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from bot import app
from database.models import User, db
from bot import app
from datetime import datetime
import logging
from bot import app

logger = logging.getLogger(__name__)

async def balance_command(update: Update, context: Context):
    """Xem s? du tài kho?n - FIX L?I MARKDOWN"""
    user = update.effective_user
    
    from main import app
from bot import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        
        if not db_user:
            text = "? KHÔNG TÌM TH?Y TÀI KHO?N\n\nVui lòng g?i /start d? dang ký."
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        balance = db_user.balance
        total_spent = db_user.total_spent
        total_rentals = db_user.total_rentals
        
        # S?A Ð?NH D?NG - B? ** không c?n thi?t
        text = (
            f"?? S? DU TÀI KHO?N\n\n"
            f"• User ID: {user.id}\n"
            f"• Tên: {user.first_name}\n"
            f"• Username: @{user.username or 'N/A'}\n\n"
            f"?? S? du hi?n t?i: {balance:,}d\n"
            f"?? Ðã thuê: {total_rentals} s?\n"
            f"?? T?ng chi: {total_spent:,}d\n\n"
            f"?? Ch?n thao tác:"
        )
        
        keyboard = [
            [InlineKeyboardButton("?? N?p ti?n", callback_data="menu_deposit")],
            [InlineKeyboardButton("?? Thuê s?", callback_data="menu_rent")],
            [InlineKeyboardButton("?? Menu chính", callback_data="menu_main")]
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
