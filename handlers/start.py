from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext as Context
from database.models import User, db
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')

async def start_command(update: Update, context: Context):
    """Xử lý lệnh /start"""
    user = update.effective_user
    
    from main import app
    with app.app_context():
        existing_user = User.query.filter_by(user_id=user.id).first()
        if not existing_user:
            new_user = User(
                user_id=user.id,
                username=user.username or user.first_name,
                balance=0,
                created_at=datetime.now(),
                last_active=datetime.now()
            )
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"✅ Người dùng mới: {user.id} - {user.first_name}")
        else:
            existing_user.last_active = datetime.now()
            db.session.commit()
            logger.info(f"🔄 Người dùng cũ: {user.id} - {user.first_name}")
    
    keyboard = [
        [InlineKeyboardButton("📱 Thuê số", callback_data='menu_rent'),
         InlineKeyboardButton("📋 Số đang thuê", callback_data='menu_rent_list')],
        [InlineKeyboardButton("💰 Số dư", callback_data='menu_balance'),
         InlineKeyboardButton("📥 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📋 Lịch sử", callback_data='menu_history'),
         InlineKeyboardButton("👤 Tài khoản", callback_data='menu_profile')],
        [InlineKeyboardButton("❓ Hướng dẫn", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""🎉 **Chào mừng {user.first_name} đến với Bot Thuê SMS!**

🤖 Bot cung cấp dịch vụ thuê số điện thoại ảo:
• Facebook • Google • Tiktok • Shopee • Các dịch vụ khác

⚠️ **TUÂN THỦ PHÁP LUẬT:**
• Nghiêm cấm lừa đảo, cá độ, bank ảo
• Vi phạm sẽ khóa tài khoản

🏦 **MBBANK**
💳 **Số TK:** `{MB_ACCOUNT}`
👤 **Chủ TK:** `{MB_NAME}`

💡 **Hướng dẫn nhanh:**
• Chọn 'Thuê số' để bắt đầu
• Chọn 'Số đang thuê' để xem các số đã thuê"""
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def menu_command(update: Update, context: Context):
    """Hiển thị menu chính"""
    query = update.callback_query
    if query:
        await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📱 Thuê số", callback_data='menu_rent'),
         InlineKeyboardButton("📋 Số đang thuê", callback_data='menu_rent_list')],
        [InlineKeyboardButton("💰 Số dư", callback_data='menu_balance'),
         InlineKeyboardButton("📥 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📋 Lịch sử", callback_data='menu_history'),
         InlineKeyboardButton("👤 Tài khoản", callback_data='menu_profile')],
        [InlineKeyboardButton("❓ Hướng dẫn", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🏠 **MENU CHÍNH**\n\nChọn chức năng bạn muốn sử dụng:"
    
    if query:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel(update: Update, context: Context):
    """Hủy thao tác hiện tại"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "✅ **ĐÃ HỦY THAO TÁC!**\n\nBạn có thể chọn chức năng khác.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 QUAY LẠI MENU", callback_data="menu_main")
            ]]),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "✅ **ĐÃ HỦY THAO TÁC!**\n\nBạn có thể chọn chức năng khác.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 QUAY LẠI MENU", callback_data="menu_main")
            ]]),
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: Context):
    """Hiển thị hướng dẫn chi tiết"""
    text = """❓ **HƯỚNG DẪN CHI TIẾT**

1️⃣ **Nạp tiền:**
   • Chọn 'Nạp tiền' → Chọn số tiền
   • Chuyển khoản đến tài khoản:
     💳 {MB_ACCOUNT} - {MB_NAME}
   • Nhập nội dung chính xác để được cộng tự động

2️⃣ **Thuê số:**
   • Chọn 'Thuê số' → Chọn dịch vụ
   • Chọn nhà mạng → Xác nhận
   • Bot tự động kiểm tra OTP trong 5 phút

3️⃣ **Quản lý số:**
   • 'Số đang thuê': Xem tất cả số đang active
   • Click vào số để xem chi tiết/hủy số
   • Hủy số được hoàn tiền (nếu chưa có OTP)

⚠️ **QUY ĐỊNH:**
• Không lừa đảo, cá độ, đánh bạc
• Không tạo bank ảo, tiền ảo
• Vi phạm sẽ khóa tài khoản vĩnh viễn

📞 **Hỗ trợ:** Liên hệ admin @makkllai"""
    
    text = text.format(MB_ACCOUNT=MB_ACCOUNT, MB_NAME=MB_NAME)
    
    keyboard = [[InlineKeyboardButton("🔙 Quay lại menu", callback_data="menu_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')