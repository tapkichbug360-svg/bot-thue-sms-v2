from flask import request, jsonify
import logging
from database.models import User, Transaction, db
from datetime import datetime
import os
import re

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')

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
            
            if transfer_type != 'in':
                return jsonify({"status": "ignored"}), 200
            
            if account_number != MB_ACCOUNT:
                return jsonify({"status": "ok"}), 200
            
            # Tìm mã NAP
            match = re.search(r'NAP\s*([A-Z0-9]{8})', content.upper())
            if not match:
                logger.warning(f"Không tìm thấy mã NAP")
                return jsonify({"status": "ok"}), 200
            
            transaction_code = match.group(1)
            logger.info(f"Mã NAP: {transaction_code}")
            
            with app.app_context():
                # Tìm transaction
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                if not transaction:
                    logger.error(f"Không tìm thấy transaction")
                    return jsonify({"status": "ok"}), 200
                
                # Kiểm tra số tiền
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"Số tiền không khớp")
                    return jsonify({"status": "ok"}), 200
                
                # Cộng tiền
                user = User.query.get(transaction.user_id)
                if not user:
                    logger.error(f"Không tìm thấy user")
                    return jsonify({"status": "ok"}), 200
                
                old_balance = user.balance
                user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("✅ NẠP TIỀN THÀNH CÔNG!")
                logger.info(f"User: {user.user_id}")
                logger.info(f"Số dư: {old_balance}đ → {user.balance}đ")
                
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            logger.error(f"LỖI: {e}")
            return jsonify({"status": "error"}), 500
