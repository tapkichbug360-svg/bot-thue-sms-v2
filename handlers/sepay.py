from flask import request, jsonify, make_response
import logging
from database.models import User, Transaction, db
from datetime import datetime
import os
import re
import asyncio
from telegram import Bot

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')
BOT_TOKEN = os.getenv('BOT_TOKEN')

telegram_bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

async def send_telegram_notification(chat_id, message):
    try:
        if telegram_bot:
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Đã gửi thông báo Telegram cho user {chat_id}")
    except Exception as e:
        logger.error(f"❌ Lỗi gửi Telegram: {e}")

def setup_sepay_webhook(app):
    @app.route('/webhook/sepay', methods=['POST'])
    def sepay_webhook():
        try:
            data = request.json
            logger.info("="*60)
            logger.info("📩 NHẬN WEBHOOK TỪ SEPAY")
            logger.info(f"Dữ liệu: {data}")
            
            transfer_type = data.get('transferType')
            account_number = data.get('accountNumber')
            amount = int(float(data.get('transferAmount', 0)))
            content = data.get('content', '').strip()
            transaction_id = data.get('transactionId', '')
            
            if transfer_type != 'in':
                return jsonify({"success": True, "message": "Ignored"}), 200
            
            if account_number != MB_ACCOUNT:
                return jsonify({"success": True, "message": "Wrong account"}), 200
            
            # Tìm mã NAP
            match = re.search(r'NAP\s*([A-Z0-9]{8})', content.upper())
            if not match:
                return jsonify({"success": True, "message": "No NAP code found"}), 200
            
            transaction_code = match.group(1)
            logger.info(f"✅ Mã NAP: {transaction_code}")
            
            with app.app_context():
                # Tìm giao dịch
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                if not transaction:
                    logger.error(f"❌ Không tìm thấy giao dịch pending: {transaction_code}")
                    
                    # Tự động tạo user và giao dịch mới nếu chưa có
                    # Tìm user_id từ nội dung? Không có, phải tạo tạm
                    # Cách xử lý: Tạo giao dịch mới với user_id = None và báo admin
                    
                    # Tìm user mặc định (admin) để gán tạm
                    admin_user = User.query.filter_by(is_admin=True).first()
                    if admin_user:
                        new_trans = Transaction(
                            user_id=admin_user.id,
                            amount=amount,
                            type='deposit',
                            status='pending',
                            transaction_code=transaction_code,
                            description=f"Webhook without pending: {content}",
                            created_at=datetime.now()
                        )
                        db.session.add(new_trans)
                        db.session.commit()
                        logger.info(f"⚠️ Đã tạo giao dịch mới cho mã {transaction_code} (chưa có pending)")
                    
                    return jsonify({"success": True, "message": "Created new transaction"}), 200
                
                # Kiểm tra số tiền
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"❌ Số tiền không khớp: {amount} != {transaction.amount}")
                    return jsonify({"success": True, "message": "Amount mismatch"}), 200
                
                # Cộng tiền
                user = User.query.get(transaction.user_id)
                if not user:
                    logger.error(f"❌ Không tìm thấy user ID: {transaction.user_id}")
                    return jsonify({"success": True, "message": "User not found"}), 200
                
                old_balance = user.balance
                user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("✅ NẠP TIỀN THÀNH CÔNG!")
                logger.info(f"User: {user.user_id} - {old_balance}đ → {user.balance}đ")
                
                # Gửi thông báo Telegram
                try:
                    message = (
                        f"💰 **NẠP TIỀN THÀNH CÔNG!**\n\n"
                        f"• **Số tiền:** `{transaction.amount:,}đ`\n"
                        f"• **Mã GD:** `{transaction_code}`\n"
                        f"• **Số dư mới:** `{user.balance:,}đ`"
                    )
                    asyncio.run(send_telegram_notification(user.user_id, message))
                except Exception as e:
                    logger.error(f"Lỗi gửi Telegram: {e}")
                
                return jsonify({
                    "success": True,
                    "message": "Deposit processed successfully",
                    "data": {
                        "user_id": user.user_id,
                        "amount": transaction.amount,
                        "new_balance": user.balance,
                        "transaction_code": transaction_code
                    }
                }), 200
            
        except Exception as e:
            logger.error(f"❌ LỖI WEBHOOK: {e}")
            return jsonify({"success": False, "error": str(e)}), 500