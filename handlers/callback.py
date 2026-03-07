from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from database.models import User, Rental
from datetime import datetime

# Import các hàm từ các handlers khác
from handlers.balance import balance_command
from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
from handlers.rent import (
    rent_command, rent_service_callback, rent_network_callback,
    rent_confirm_callback, rent_check_callback, rent_cancel_callback,
    rent_list_callback, rent_view_callback
)

async def menu_callback(update: Update, context: Context):
    """Xử lý tất cả các callback từ menu - FIX LỖI MARKDOWN"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    data = query.data
    
    if data == 'menu_main':
        keyboard = [
            [InlineKeyboardButton("📱 Thuê số", callback_data='menu_rent'),
             InlineKeyboardButton("📋 Số đang thuê", callback_data='menu_rent_list')],
            [InlineKeyboardButton("💰 Số dư", callback_data='menu_balance'),
             InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit')],
            [InlineKeyboardButton("📜 Lịch sử", callback_data='menu_history'),
             InlineKeyboardButton("👤 Tài khoản", callback_data='menu_profile')],
            [InlineKeyboardButton("❓ Hướng dẫn", callback_data='menu_help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🎯 MENU CHÍNH"
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
        with app.app_context():
            rentals = Rental.query.filter_by(user_id=user.id).order_by(Rental.created_at.desc()).limit(10).all()
        
        if not rentals:
            text = "📜 LỊCH SỬ\n\nChưa có giao dịch nào."
        else:
            text = "📜 LỊCH SỬ GIAO DỊCH\n\n"
            for r in rentals:
                status_icon = {
                    'waiting': '⏳',
                    'success': '✅',
                    'cancelled': '❌',
                    'expired': '⏰'
                }.get(r.status, '❓')
                text += f"{status_icon} {r.created_at.strftime('%H:%M %d/%m')} - {r.service_name}\n"
                if r.phone_number:
                    text += f"   📞 {r.phone_number}\n"
                if r.otp_code and r.status == 'success':
                    text += f"   🔑 OTP: {r.otp_code}\n"
                text += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main')]]
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
        text = """❓ HƯỚNG DẪN SỬ DỤNG

1️⃣ Nạp tiền:
   • Chọn 'Nạp tiền' → Chọn số tiền
   • Chuyển khoản đến số tài khoản bên dưới
   • Nhập nội dung chính xác để được cộng tự động

2️⃣ Thuê số:
   • Chọn 'Thuê số' → Chọn dịch vụ
   • Chọn nhà mạng → Xác nhận
   • Bot sẽ tự động kiểm tra OTP trong 5 phút

3️⃣ Quản lý số:
   • 'Số đang thuê': Xem tất cả số đang active
   • Click vào số để xem chi tiết/hủy số

⚠️ TUÂN THỦ PHÁP LUẬT:
• Nghiêm cấm lừa đảo, cá độ, đánh bạc
• Không tạo bank ảo, tiền ảo
• Vi phạm sẽ khóa tài khoản vĩnh viễn

🏦 TK MBBank: 666666291005 - NGUYEN THE LAM
📞 Hỗ trợ: @makkllai"""
        
        keyboard = [[InlineKeyboardButton("🔙 Quay lại menu", callback_data="menu_main")]]
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
        with app.app_context():
            db_user = User.query.filter_by(user_id=user.id).first()
            balance = db_user.balance if db_user else 0
            total_rentals = db_user.total_rentals if db_user else 0
            total_spent = db_user.total_spent if db_user else 0
            created_at = db_user.created_at if db_user else datetime.now()
        
        text = f"""👤 THÔNG TIN TÀI KHOẢN

• ID: {user.id}
• Tên: {user.first_name}
• Username: @{user.username or 'N/A'}
• Ngày tham gia: {created_at.strftime('%d/%m/%Y')}

📊 THỐNG KÊ:
• Số dư: {balance:,}đ
• Đã thuê: {total_rentals} số
• Đã chi: {total_spent:,}đ"""
        
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup
            )