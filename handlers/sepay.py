from flask import request, jsonify
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
            logger.info("="*50)
            logger.info("📩 NHẬN WEBHOOK TỪ SEPAY")
            logger.info(f"Dữ liệu: {data}")
            
            transfer_type = data.get('transferType')
            account_number = data.get('accountNumber')
            amount = int(float(data.get('transferAmount', 0)))
            content = data.get('content', '').strip()
            transaction_id = data.get('transactionId', '')
            
            logger.info(f"Loại: {transfer_type}")
            logger.info(f"TK: {account_number}")
            logger.info(f"Tiền: {amount}đ")
            logger.info(f"Nội dung: {content}")
            logger.info(f"Mã GD SePay: {transaction_id}")
            
            if transfer_type != 'in':
                logger.info(f"⏭️ Bỏ qua giao dịch loại {transfer_type}")
                # QUAN TRỌNG: Phải trả về response đầy đủ
                return jsonify({"success": True, "message": "Ignored"}), 200
            
            if account_number != MB_ACCOUNT:
                logger.info(f"⏭️ Không phải tài khoản nhận")
                return jsonify({"success": True, "message": "Wrong account"}), 200
            
            # Tìm mã NAP
            match = re.search(r'NAP\s*([A-Z0-9]{8})', content.upper())
            if not match:
                logger.warning(f"❌ Không tìm thấy mã NAP")
                return jsonify({"success": True, "message": "No NAP code found"}), 200
            
            transaction_code = match.group(1)
            logger.info(f"Mã NAP: {transaction_code}")
            
            with app.app_context():
                # Tìm transaction
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                if not transaction:
                    logger.error(f"❌ Không tìm thấy transaction")
                    return jsonify({"success": True, "message": "Transaction not found"}), 200
                
                # Kiểm tra số tiền
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"❌ Số tiền không khớp")
                    return jsonify({"success": True, "message": "Amount mismatch"}), 200
                
                # Cộng tiền
                user = User.query.get(transaction.user_id)
                if not user:
                    logger.error(f"❌ Không tìm thấy user")
                    return jsonify({"success": True, "message": "User not found"}), 200
                
                old_balance = user.balance
                user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("✅ NẠP TIỀN THÀNH CÔNG!")
                logger.info(f"User: {user.user_id}")
                logger.info(f"Số dư: {old_balance}đ → {user.balance}đ")
                
                # Gửi thông báo Telegram
                try:
                    message = (
                        f"💰 **NẠP TIỀN THÀNH CÔNG!**\n\n"
                        f"• **Số tiền:** {transaction.amount:,}đ\n"
                        f"• **Mã GD:** {transaction_code}\n"
                        f"• **Số dư cũ:** {old_balance:,}đ\n"
                        f"• **Số dư mới:** {user.balance:,}đ\n"
                        f"• **Thời gian:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
                    )
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(send_telegram_notification(user.user_id, message))
                    loop.close()
                except Exception as e:
                    logger.error(f"Lỗi gửi Telegram: {e}")
                
                # QUAN TRỌNG: Trả về response đầy đủ
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
            logger.error(f"LỖI: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
