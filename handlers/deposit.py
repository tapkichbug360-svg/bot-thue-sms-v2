from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext as Context
from database.models import User, Transaction, db
from datetime import datetime
import logging
import random
import string
import os

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')
MB_BIN = os.getenv('MB_BIN', '970422')

async def deposit_command(update: Update, context: Context):
    """Hiển thị menu nạp tiền"""
    transaction_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data['pending_deposit'] = {'code': transaction_code, 'amount': None}
    
    amounts = [20000, 50000, 100000, 200000, 500000, 1000000]
    keyboard = []
    row = []
    for i, amount in enumerate(amounts):
        btn = InlineKeyboardButton(f"{amount:,}đ", callback_data=f"deposit_amount_{amount}")
        row.append(btn)
        if len(row) == 2 or i == len(amounts)-1:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("🔙 Quay lại menu chính", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🏦 **NẠP TIỀN QUA MBBANK**

💳 **Số TK:** {MB_ACCOUNT}
👤 **Chủ TK:** {MB_NAME}
🏦 **Ngân hàng:** MBBank

📝 **Nội dung:** NAP {transaction_code}

💰 **Chọn số tiền:**"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def deposit_amount_callback(update: Update, context: Context):
    """Xử lý khi chọn số tiền"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    try:
        amount = int(query.data.split('_')[2])
        pending = context.user_data.get('pending_deposit', {})
        transaction_code = pending.get('code')
        
        if not transaction_code:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="❌ Có lỗi xảy ra! Vui lòng thử lại."
            )
            return
        
        # Lưu giao dịch vào database
        from main import app
        with app.app_context():
            user = update.effective_user
            
            # Tìm hoặc tạo user
            db_user = User.query.filter_by(user_id=user.id).first()
            if not db_user:
                db_user = User(
                    user_id=user.id,
                    username=user.username or user.first_name,
                    balance=0,
                    created_at=datetime.now()
                )
                db.session.add(db_user)
                db.session.commit()
                logger.info(f"✅ Đã tạo user mới: {user.id}")
            
            # Tạo transaction
            transaction = Transaction(
                user_id=db_user.id,
                amount=amount,
                type='deposit',
                status='pending',
                transaction_code=transaction_code,
                description=f'Nạp {amount}đ qua MBBank',
                created_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"✅ ĐÃ TẠO GIAO DỊCH: {transaction_code} - {amount}đ cho user {user.id}")
        
        # Tạo QR code
        content = f"NAP {transaction_code}"
        qr_url = f"https://img.vietqr.io/image/{MB_BIN}-{MB_ACCOUNT}-compact2.png?amount={amount}&addInfo={content}&accountName={MB_NAME}"
        
        keyboard = [
            [InlineKeyboardButton("✅ TÔI ĐÃ CHUYỂN KHOẢN", callback_data=f"deposit_check_{transaction_code}")],
            [InlineKeyboardButton("💰 Nạp số khác", callback_data="menu_deposit")],
            [InlineKeyboardButton("📱 Thuê số", callback_data="menu_rent")],
            [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=qr_url,
            caption=f"""🏦 **THÔNG TIN CHUYỂN KHOẢN**

💳 **STK:** {MB_ACCOUNT}
👤 **Chủ TK:** {MB_NAME}
💰 **Số tiền:** {amount:,}đ
📝 **Nội dung:** {content}

✅ **Bấm nút 'TÔI ĐÃ CHUYỂN KHOẢN' sau khi chuyển!""",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        await query.delete_message()
        
    except Exception as e:
        logger.error(f"Lỗi deposit_amount_callback: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="❌ Có lỗi xảy ra! Vui lòng thử lại."
        )

async def deposit_check_callback(update: Update, context: Context):
    """Xử lý khi user bấm 'TÔI ĐÃ CHUYỂN KHOẢN'"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    try:
        transaction_code = query.data.split('_')[2]
        logger.info(f"👤 User báo đã chuyển khoản - Mã GD: {transaction_code}")
        
        from main import app
        with app.app_context():
            transaction = Transaction.query.filter_by(
                transaction_code=transaction_code, 
                status='pending'
            ).first()
            
            if not transaction:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ **KHÔNG TÌM THẤY GIAO DỊCH**\n\nMã GD: {transaction_code}",
                    parse_mode='Markdown'
                )
                return
            
            transaction.updated_at = datetime.now()
            db.session.commit()
            
            text = f"""⏳ **ĐANG CHỜ XÁC NHẬN TỪ NGÂN HÀNG**

💰 **Số tiền:** {transaction.amount:,}đ
📝 **Mã GD:** {transaction_code}

✅ Đã ghi nhận yêu cầu nạp tiền của bạn.
⏱️ Hệ thống sẽ **TỰ ĐỘNG CỘNG TIỀN** sau khi xác nhận giao dịch thành công từ ngân hàng.

⏰ **Thời gian xử lý:** 1-5 phút
⚠️ **KHÔNG CẦN BẤM NÚT NHIỀU LẦN**"""
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Lỗi deposit_check_callback: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ **LỖI XỬ LÝ**\n\nVui lòng thử lại sau.",
            parse_mode='Markdown'
        )
