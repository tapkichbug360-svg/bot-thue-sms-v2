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
    """Gửi thông báo Telegram bất đồng bộ"""
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
        """Xử lý webhook từ SePay - FIX CUỐI CÙNG với make_response"""
        try:
            # Lấy dữ liệu từ request
            data = request.json
            logger.info("="*60)
            logger.info("📩 NHẬN WEBHOOK TỪ SEPAY")
            logger.info(f"Dữ liệu nhận được: {data}")
            
            # Lấy thông tin giao dịch
            transfer_type = data.get('transferType')
            account_number = data.get('accountNumber')
            amount = int(float(data.get('transferAmount', 0)))
            content = data.get('content', '').strip()
            transaction_id = data.get('transactionId', '')
            
            logger.info(f"Loại giao dịch: {transfer_type}")
            logger.info(f"Tài khoản nhận: {account_number}")
            logger.info(f"Số tiền: {amount}đ")
            logger.info(f"Nội dung: {content}")
            logger.info(f"Mã GD SePay: {transaction_id}")
            
            # Chỉ xử lý giao dịch đến (in)
            if transfer_type != 'in':
                logger.info(f"⏭️ Bỏ qua giao dịch loại {transfer_type}")
                response_data = {"success": True, "message": "Ignored"}
                response = make_response(jsonify(response_data), 200)
                response.headers['Content-Type'] = 'application/json'
                logger.info(f"📤 Response gửi đi: {response_data}")
                return response
            
            # Kiểm tra tài khoản nhận
            if account_number != MB_ACCOUNT:
                logger.info(f"⏭️ Không phải tài khoản nhận")
                response_data = {"success": True, "message": "Wrong account"}
                response = make_response(jsonify(response_data), 200)
                response.headers['Content-Type'] = 'application/json'
                logger.info(f"📤 Response gửi đi: {response_data}")
                return response
            
            # Tìm mã NAP trong nội dung
            match = re.search(r'NAP\s*([A-Z0-9]{8})', content.upper())
            if not match:
                logger.warning(f"❌ Không tìm thấy mã NAP trong nội dung: {content}")
                response_data = {"success": True, "message": "No NAP code found"}
                response = make_response(jsonify(response_data), 200)
                response.headers['Content-Type'] = 'application/json'
                logger.info(f"📤 Response gửi đi: {response_data}")
                return response
            
            transaction_code = match.group(1)
            logger.info(f"✅ Tìm thấy mã NAP: {transaction_code}")
            
            # Xử lý trong app context
            with app.app_context():
                # Tìm giao dịch pending
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                if not transaction:
                    logger.error(f"❌ Không tìm thấy giao dịch pending với mã: {transaction_code}")
                    response_data = {"success": True, "message": "Transaction not found"}
                    response = make_response(jsonify(response_data), 200)
                    response.headers['Content-Type'] = 'application/json'
                    logger.info(f"📤 Response gửi đi: {response_data}")
                    return response
                
                # Kiểm tra số tiền (cho phép sai số 5000đ)
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"❌ Số tiền không khớp: {amount} != {transaction.amount}")
                    response_data = {"success": True, "message": "Amount mismatch"}
                    response = make_response(jsonify(response_data), 200)
                    response.headers['Content-Type'] = 'application/json'
                    logger.info(f"📤 Response gửi đi: {response_data}")
                    return response
                
                # Tìm user
                user = User.query.get(transaction.user_id)
                if not user:
                    logger.error(f"❌ Không tìm thấy user ID: {transaction.user_id}")
                    response_data = {"success": True, "message": "User not found"}
                    response = make_response(jsonify(response_data), 200)
                    response.headers['Content-Type'] = 'application/json'
                    logger.info(f"📤 Response gửi đi: {response_data}")
                    return response
                
                # Cộng tiền
                old_balance = user.balance
                user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("="*60)
                logger.info("✅ NẠP TIỀN THÀNH CÔNG!")
                logger.info(f"👤 User: {user.user_id}")
                logger.info(f"💰 Số dư cũ: {old_balance:,}đ")
                logger.info(f"💰 Số dư mới: {user.balance:,}đ")
                logger.info(f"💳 Mã GD: {transaction_code}")
                logger.info("="*60)
                
                # Gửi thông báo Telegram
                try:
                    message = (
                        f"💰 **NẠP TIỀN THÀNH CÔNG!**\n\n"
                        f"• **Số tiền:** `{transaction.amount:,}đ`\n"
                        f"• **Mã GD:** `{transaction_code}`\n"
                        f"• **Số dư cũ:** `{old_balance:,}đ`\n"
                        f"• **Số dư mới:** `{user.balance:,}đ`\n"
                        f"• **Thời gian:** `{datetime.now().strftime('%H:%M:%S %d/%m/%Y')}`"
                    )
                    
                    # Tạo event loop mới để gửi async
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(send_telegram_notification(user.user_id, message))
                    loop.close()
                    
                except Exception as e:
                    logger.error(f"❌ Lỗi gửi thông báo Telegram: {e}")
                
                # Tạo response thành công với đầy đủ dữ liệu
                response_data = {
                    "success": True,
                    "message": "Deposit processed successfully",
                    "data": {
                        "user_id": user.user_id,
                        "amount": transaction.amount,
                        "new_balance": user.balance,
                        "transaction_code": transaction_code,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                response = make_response(jsonify(response_data), 200)
                response.headers['Content-Type'] = 'application/json'
                logger.info(f"📤 Response gửi đi: {response_data}")
                return response
            
        except Exception as e:
            logger.error(f"❌ LỖI XỬ LÝ WEBHOOK: {e}")
            import traceback
            traceback.print_exc()
            
            response_data = {
                "success": False,
                "error": str(e)
            }
            response = make_response(jsonify(response_data), 500)
            response.headers['Content-Type'] = 'application/json'
            logger.info(f"📤 Response gửi đi: {response_data}")
            return response