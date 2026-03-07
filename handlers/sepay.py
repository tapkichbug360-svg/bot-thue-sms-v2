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
                # BƯỚC 1: Tìm giao dịch pending với mã này
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                # BƯỚC 2: XÁC ĐỊNH USER - CHỈ TÌM, KHÔNG TẠO MỚI
                target_user = None
                
                if transaction:
                    # Nếu có giao dịch pending, lấy user từ giao dịch đó
                    target_user = User.query.get(transaction.user_id)
                    logger.info(f"🔍 Tìm thấy giao dịch pending, user: {target_user.user_id if target_user else 'None'}")
                else:
                    # KHÔNG CÓ GIAO DỊCH PENDING - Tìm user từ nhiều nguồn
                    logger.info(f"🔍 Không tìm thấy giao dịch pending, tìm user từ các nguồn...")
                    
                    # Cách 1: Tìm user_id trong nội dung (QUAN TRỌNG NHẤT)
                    user_match = re.search(r'tu (\d+)', content)
                    if user_match:
                        found_user_id = int(user_match.group(1))
                        target_user = User.query.filter_by(user_id=found_user_id).first()
                        if target_user:
                            logger.info(f"✅ Cách 1: Tìm thấy user từ nội dung: {target_user.user_id}")
                    
                    # Cách 2: Tìm user có giao dịch pending với mã này
                    if not target_user:
                        pending_trans = Transaction.query.filter_by(
                            transaction_code=transaction_code,
                            status='pending'
                        ).first()
                        if pending_trans:
                            target_user = User.query.get(pending_trans.user_id)
                            logger.info(f"✅ Cách 2: Tìm thấy user từ giao dịch pending: {target_user.user_id if target_user else 'None'}")
                    
                    # Cách 3: Tìm user có username trong nội dung
                    if not target_user:
                        all_users = User.query.all()
                        for u in all_users:
                            if u.username and u.username in content:
                                target_user = u
                                logger.info(f"✅ Cách 3: Tìm thấy user từ username: {target_user.user_id}")
                                break
                    
                    # Cách 4: Tìm user từ transaction_code trong bất kỳ giao dịch nào
                    if not target_user:
                        any_trans = Transaction.query.filter_by(
                            transaction_code=transaction_code
                        ).first()
                        if any_trans:
                            target_user = User.query.get(any_trans.user_id)
                            logger.info(f"✅ Cách 4: Tìm thấy user từ giao dịch cũ: {target_user.user_id if target_user else 'None'}")
                    
                    # Cách 5: Tìm user có user_id gần với mã giao dịch (dự phòng)
                    if not target_user:
                        # Thử tìm user có user_id xuất hiện trong content
                        import re
                        numbers = re.findall(r'\d+', content)
                        for num in numbers:
                            if len(num) >= 9:  # User ID thường có 10 số
                                potential_user = User.query.filter_by(user_id=int(num)).first()
                                if potential_user:
                                    target_user = potential_user
                                    logger.info(f"✅ Cách 5: Tìm thấy user từ số trong nội dung: {target_user.user_id}")
                                    break
                
                # NẾU KHÔNG TÌM THẤY USER - TRẢ VỀ LỖI
                if not target_user:
                    logger.error(f"❌ KHÔNG TÌM THẤY USER cho giao dịch {transaction_code}")
                    return jsonify({
                        "success": False,
                        "message": "User not found",
                        "error": "No matching user found for this transaction. Please start the bot first."
                    }), 404
                
                # BƯỚC 3: XỬ LÝ GIAO DỊCH
                if not transaction:
                    # Tạo giao dịch mới cho user đã tìm thấy
                    transaction = Transaction(
                        user_id=target_user.id,
                        amount=amount,
                        type='deposit',
                        status='pending',
                        transaction_code=transaction_code,
                        description=f"Auto-created from webhook",
                        created_at=datetime.now()
                    )
                    db.session.add(transaction)
                    db.session.flush()
                    logger.info(f"✅ ĐÃ TẠO GIAO DỊCH MỚI: {transaction_code} cho user {target_user.user_id}")
                
                # KIỂM TRA SỐ TIỀN (cho phép sai số 5000đ)
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"❌ Số tiền không khớp: {amount} != {transaction.amount}")
                    return jsonify({"success": True, "message": "Amount mismatch"}), 200
                
                # CỘNG TIỀN
                old_balance = target_user.balance
                target_user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("✅ NẠP TIỀN THÀNH CÔNG!")
                logger.info(f"👤 User: {target_user.user_id} - {target_user.username}")
                logger.info(f"💰 Số dư: {old_balance}đ → {target_user.balance}đ")
                logger.info(f"💳 Mã GD: {transaction_code}")
                
                # Gửi thông báo Telegram
                if BOT_TOKEN:
                    try:
                        message = (
                            f"💰 **NẠP TIỀN THÀNH CÔNG!**\n\n"
                            f"• **Số tiền:** `{transaction.amount:,}đ`\n"
                            f"• **Mã GD:** `{transaction_code}`\n"
                            f"• **Số dư mới:** `{target_user.balance:,}đ`\n"
                            f"• **Thời gian:** `{datetime.now().strftime('%H:%M:%S %d/%m/%Y')}`"
                        )
                        asyncio.run(send_telegram_notification(target_user.user_id, message))
                    except Exception as e:
                        logger.error(f"Lỗi gửi Telegram: {e}")
                
                return jsonify({
                    "success": True,
                    "message": "Deposit processed successfully",
                    "data": {
                        "user_id": target_user.user_id,
                        "amount": transaction.amount,
                        "new_balance": target_user.balance,
                        "transaction_code": transaction_code,
                        "timestamp": datetime.now().isoformat()
                    }
                }), 200
            
        except Exception as e:
            logger.error(f"❌ LỖI WEBHOOK: {e}")
            return jsonify({"success": False, "error": str(e)}), 500