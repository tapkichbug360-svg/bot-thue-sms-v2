from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from bot import app
from database.models import User, Rental
from bot import app
from datetime import datetime
from bot import app

# Import các hàm t? các handlers khác
from bot import app
from handlers.balance import balance_command
from bot import app
from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
from bot import app
from handlers.rent import (
from bot import app
    rent_command, rent_service_callback, rent_network_callback,
    rent_confirm_callback, rent_check_callback, rent_cancel_callback,
    rent_list_callback, rent_view_callback
)

async def menu_callback(update: Update, context: Context):
    """X? lý t?t c? các callback t? menu - FIX L?I MARKDOWN"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    data = query.data
    
    if data == 'menu_main':
        keyboard = [
            [InlineKeyboardButton("?? Thuê s?", callback_data='menu_rent'),
             InlineKeyboardButton("?? S? dang thuê", callback_data='menu_rent_list')],
            [InlineKeyboardButton("?? S? du", callback_data='menu_balance'),
             InlineKeyboardButton("?? N?p ti?n", callback_data='menu_deposit')],
            [InlineKeyboardButton("?? L?ch s?", callback_data='menu_history'),
             InlineKeyboardButton("?? Tài kho?n", callback_data='menu_profile')],
            [InlineKeyboardButton("? Hu?ng d?n", callback_data='menu_help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "?? MENU CHÍNH"  # B? **
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup
            )
    
    elif data == 'menu_balance':
        await balance_command(update, context)
    
    elif data == 'menu_deposit':
        await deposit_command(update, context)
    
    elif data.startswith('deposit_amount_'):
        await deposit_amount_callback(update, context)
    
    elif data.startswith('deposit_check_'):
        await deposit_check_callback(update, context)
    
    elif data == 'menu_rent':
        await rent_command(update, context)
    
    elif data == 'menu_rent_list':
        await rent_list_callback(update, context)
    
    elif data.startswith('rent_service_'):
        await rent_service_callback(update, context)
    
    elif data.startswith('rent_network_'):
        await rent_network_callback(update, context)
    
    elif data.startswith('rent_confirm_'):
        await rent_confirm_callback(update, context)
    
    elif data.startswith('rent_check_'):
        await rent_check_callback(update, context)
    
    elif data.startswith('rent_cancel_'):
        await rent_cancel_callback(update, context)
    
    elif data.startswith('rent_view_'):
        await rent_view_callback(update, context)
    
    elif data == 'menu_history':
        user = update.effective_user
        from main import app
from bot import app
        with app.app_context():
            rentals = Rental.query.filter_by(user_id=user.id).order_by(Rental.created_at.desc()).limit(10).all()
        
        if not rentals:
            text = "?? L?CH S?\n\nChua có giao d?ch nào."
        else:
            text = "?? L?CH S? GIAO D?CH\n\n"
            for r in rentals:
                status_icon = {
                    'waiting': '?',
                    'success': '?',
                    'cancelled': '?',
                    'expired': '?'
                }.get(r.status, '?')
                text += f"{status_icon} {r.created_at.strftime('%H:%M %d/%m')} - {r.service_name}\n"
                if r.phone_number:
                    text += f"   ?? {r.phone_number}\n"
                if r.otp_code and r.status == 'success':
                    text += f"   ?? OTP: {r.otp_code}\n"
                text += "\n"
        
        keyboard = [[InlineKeyboardButton("?? Quay l?i", callback_data='menu_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup
            )
    
    elif data == 'menu_help':
        text = """? HU?NG D?N S? D?NG

1?? N?p ti?n:
   • Ch?n 'N?p ti?n' ? Ch?n s? ti?n
   • Chuy?n kho?n d?n s? tài kho?n bên du?i
   • Nh?p n?i dung chính xác d? du?c c?ng t? d?ng

2?? Thuê s?:
   • Ch?n 'Thuê s?' ? Ch?n d?ch v?
   • Ch?n nhà m?ng ? Xác nh?n
   • Bot s? t? d?ng ki?m tra OTP trong 5 phút

3?? Qu?n lý s?:
   • 'S? dang thuê': Xem t?t c? s? dang active
   • Click vào s? d? xem chi ti?t/h?y s?

?? TUÂN TH? PHÁP LU?T:
• Nghiêm c?m l?a d?o, cá d?, dánh b?c
• Không t?o bank ?o, ti?n ?o
• Vi ph?m s? khóa tài kho?n vinh vi?n

?? TK MBBank: 666666291005 - NGUYEN THE LAM
?? H? tr?: @makkllai"""
        
        keyboard = [[InlineKeyboardButton("?? Quay l?i menu", callback_data="menu_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup
            )
    
    elif data == 'menu_profile':
        user = update.effective_user
        from main import app
from bot import app
        with app.app_context():
            db_user = User.query.filter_by(user_id=user.id).first()
            balance = db_user.balance if db_user else 0
            total_rentals = db_user.total_rentals if db_user else 0
            total_spent = db_user.total_spent if db_user else 0
            created_at = db_user.created_at if db_user else datetime.now()
        
        text = f"""?? THÔNG TIN TÀI KHO?N

• ID: {user.id}
• Tên: {user.first_name}
• Username: @{user.username or 'N/A'}
• Ngày tham gia: {created_at.strftime('%d/%m/%Y')}

?? TH?NG KÊ:
• S? du: {balance:,}d
• Ðã thuê: {total_rentals} s?
• Ðã chi: {total_spent:,}d"""
        
        keyboard = [[InlineKeyboardButton("?? Quay l?i", callback_data='menu_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup
            )
