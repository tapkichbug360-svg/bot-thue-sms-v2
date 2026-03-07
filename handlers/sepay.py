from flask import request, jsonify, make_response
import logging
from bot import app
from database.models import User, Transaction, db
from bot import app
from datetime import datetime
import os
import re
import asyncio
from bot import app
from telegram import Bot
from bot import app

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
            logger.info(f"? Ðã g?i thông báo Telegram cho user {chat_id}")
    except Exception as e:
        logger.error(f"? L?i g?i Telegram: {e}")

def setup_sepay_webhook(app):
    @app.route('/webhook/sepay', methods=['POST'])
    def sepay_webhook():
        try:
            data = request.json
            logger.info("="*60)
            logger.info("?? NH?N WEBHOOK T? SEPAY")
            logger.info(f"D? li?u: {data}")
            
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
            logger.info(f"? Mã NAP: {transaction_code}")
            
            with app.app_context():
                # BU?C 1: Tìm giao d?ch pending v?i mã này
                transaction = Transaction.query.filter_by(
                    transaction_code=transaction_code,
                    status='pending'
                ).first()
                
                # BU?C 2: XÁC Ð?NH USER - TÌM THEO NHI?U CÁCH
                target_user = None
                
                # CÁCH 1: T? giao d?ch pending (QUAN TR?NG NH?T)
                if transaction:
                    target_user = User.query.get(transaction.user_id)
                    logger.info(f"? Cách 1: Tìm th?y user t? giao d?ch pending: {target_user.user_id if target_user else 'None'}")
                
                # CÁCH 2: Tìm user_id trong n?i dung
                if not target_user:
                    user_match = re.search(r'tu (\d+)', content)
                    if user_match:
                        found_user_id = int(user_match.group(1))
                        target_user = User.query.filter_by(user_id=found_user_id).first()
                        if target_user:
                            logger.info(f"? Cách 2: Tìm th?y user t? n?i dung: {target_user.user_id}")
                
                # CÁCH 3: Tìm user t? giao d?ch cu (QUAN TR?NG CHO USER M?I)
                if not target_user:
                    any_trans = Transaction.query.filter_by(
                        transaction_code=transaction_code
                    ).first()
                    if any_trans:
                        target_user = User.query.get(any_trans.user_id)
                        logger.info(f"? Cách 3: Tìm th?y user t? giao d?ch cu: {target_user.user_id if target_user else 'None'}")
                
                # CÁCH 4: Tìm user t? s? di?n tho?i trong n?i dung
                if not target_user:
                    numbers = re.findall(r'\d+', content)
                    for num in numbers:
                        if len(num) >= 9:  # User ID thu?ng có 10 s?
                            try:
                                potential_user = User.query.filter_by(user_id=int(num)).first()
                                if potential_user:
                                    target_user = potential_user
                                    logger.info(f"? Cách 4: Tìm th?y user t? s? {num}: {target_user.user_id}")
                                    break
                            except:
                                pass
                
                # N?U V?N KHÔNG TÌM TH?Y, T?O USER M?I T? MÃ GD
                if not target_user:
                    # T?o user m?i t? mã giao d?ch
                    import hashlib
from bot import app
                    hash_obj = hashlib.md5(transaction_code.encode())
                    new_user_id = int(hash_obj.hexdigest()[:8], 16) % 1000000000
                    
                    target_user = User(
                        user_id=new_user_id,
                        username=f"user_{transaction_code[:4]}",
                        balance=0,
                        created_at=datetime.now(),
                        last_active=datetime.now()
                    )
                    db.session.add(target_user)
                    db.session.flush()
                    logger.info(f"?? Cách 5: T?O USER M?I T? MÃ GD: {target_user.user_id}")
                
                # BU?C 3: X? LÝ GIAO D?CH
                if not transaction:
                    # T?o giao d?ch m?i cho user dã tìm th?y
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
                    logger.info(f"? ÐÃ T?O GIAO D?CH M?I: {transaction_code} cho user {target_user.user_id}")
                
                # KI?M TRA S? TI?N
                if abs(transaction.amount - amount) > 5000:
                    logger.error(f"? S? ti?n không kh?p: {amount} != {transaction.amount}")
                    return jsonify({"success": True, "message": "Amount mismatch"}), 200
                
                # C?NG TI?N
                old_balance = target_user.balance
                target_user.balance += transaction.amount
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
                
                db.session.commit()
                
                logger.info("? N?P TI?N THÀNH CÔNG!")
                logger.info(f"?? User: {target_user.user_id} - {target_user.username}")
                logger.info(f"?? S? du: {old_balance}d ? {target_user.balance}d")
                logger.info(f"?? Mã GD: {transaction_code}")
                
                # G?i thông báo Telegram
                if BOT_TOKEN:
                    try:
                        message = (
                            f"?? **N?P TI?N THÀNH CÔNG!**\n\n"
                            f"• **S? ti?n:** `{transaction.amount:,}d`\n"
                            f"• **Mã GD:** `{transaction_code}`\n"
                            f"• **S? du m?i:** `{target_user.balance:,}d`"
                        )
                        asyncio.run(send_telegram_notification(target_user.user_id, message))
                    except Exception as e:
                        logger.error(f"L?i g?i Telegram: {e}")
                
                return jsonify({
                    "success": True,
                    "message": "Deposit processed successfully",
                    "data": {
                        "user_id": target_user.user_id,
                        "amount": transaction.amount,
                        "new_balance": target_user.balance,
                        "transaction_code": transaction_code
                    }
                }), 200
            
        except Exception as e:
            logger.error(f"? L?I WEBHOOK: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
