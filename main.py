import logging
import os
import sys
import atexit
import asyncio
import time
from datetime import datetime
from flask import Flask, request, jsonify
from database.models import db, User, Rental, Transaction
from handlers.sepay import setup_sepay_webhook
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

# Telegram imports
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update

# Import từ handlers
from handlers.start import start_command, menu_command, cancel, help_command
from handlers.rent import (
    rent_command, rent_service_callback, rent_network_callback,
    rent_confirm_callback, rent_check_callback, rent_view_callback,
    rent_cancel_callback, rent_list_callback
)
from handlers.balance import balance_command
from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
from handlers.callback import menu_callback

# Tạo thư mục database
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

# Đọc file .env
print("Đang đọc file .env...")
try:
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value.strip()
                print(f"Đã đọc: {key}")
except Exception as e:
    print(f"LỖI ĐỌC FILE .ENV: {e}")
    sys.exit(1)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'bot.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    try:
        db.create_all()
        logger.info("✅ ĐÃ TẠO DATABASE THÀNH CÔNG!")
    except Exception as e:
        if "already exists" in str(e):
            logger.info("ℹ️ Database đã tồn tại")
        else:
            logger.error(f"LỖI TẠO DATABASE: {e}")

setup_sepay_webhook(app)

@app.route('/')
def home():
    return "Bot đang chạy! MBBank: 666666291005 - NGUYEN THE LAM"

# ===== HÀM KIỂM TRA SỐ HẾT HẠN =====
def check_expired_rentals():
    """Kiểm tra và tự động hoàn tiền cho các số hết hạn"""
    with app.app_context():
        try:
            expired_rentals = Rental.query.filter(
                Rental.status == 'waiting',
                Rental.expires_at < datetime.now()
            ).all()

            for rental in expired_rentals:
                user = User.query.filter_by(user_id=rental.user_id).first()
                if user:
                    refund = rental.price_charged
                    old_balance = user.balance
                    user.balance += refund
                    rental.status = 'expired'
                    rental.updated_at = datetime.now()
                    db.session.commit()

                    logger.info(f"💰 TỰ ĐỘNG HOÀN {refund}đ CHO USER {user.user_id} (số {rental.phone_number} hết hạn)")
                    
                    # Gửi thông báo Telegram
                    try:
                        bot = Bot(token=os.getenv('BOT_TOKEN'))
                        message = (
                            f"⏰ **SỐ HẾT HẠN & HOÀN TIỀN**\n\n"
                            f"• **Số:** `{rental.phone_number}`\n"
                            f"• **Dịch vụ:** {rental.service_name}\n"
                            f"• **Tiền hoàn:** `{refund:,}đ`\n"
                            f"• **Số dư mới:** `{user.balance:,}đ`"
                        )
                        asyncio.run(bot.send_message(chat_id=user.user_id, text=message, parse_mode='Markdown'))
                    except Exception as e:
                        logger.error(f"Lỗi gửi Telegram: {e}")
                else:
                    logger.error(f"❌ Không tìm thấy user {rental.user_id} để hoàn tiền")
        except Exception as e:
            logger.error(f"Lỗi kiểm tra số hết hạn: {e}")

# ===== THIẾT LẬP SCHEDULER =====
def setup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(
        func=check_expired_rentals,
        trigger=IntervalTrigger(minutes=5),
        id='check_expired_rentals',
        name='Kiểm tra số hết hạn và hoàn tiền',
        replace_existing=True
    )
    atexit.register(lambda: scheduler.shutdown())
    logger.info("⏰ Scheduler kiểm tra số hết hạn đã được khởi động (5 phút/lần)")

setup_scheduler()

# ===== API TEST NẠP TIỀN (CÓ THÔNG BÁO) =====
@app.route('/test-deposit', methods=['POST'])
def test_deposit():
    try:
        data = request.json
        user_id = data.get('user_id')
        amount = data.get('amount')
        code = data.get('code')

        with app.app_context():
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                return jsonify({"error": "User not found"}), 404

            old_balance = user.balance
            user.balance += amount

            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                type='deposit',
                status='success',
                transaction_code=code,
                description=f"Test nạp {amount}đ",
                created_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()

            logger.info(f"✅ TEST: ĐÃ CỘNG {amount}đ CHO USER {user_id}")

            # Gửi thông báo Telegram
            try:
                bot = Bot(token=os.getenv('BOT_TOKEN'))
                message = (
                    f"💰 **NẠP TIỀN THÀNH CÔNG (TEST)!**\n\n"
                    f"• **Số tiền:** `{amount:,}đ`\n"
                    f"• **Mã GD:** `{code}`\n"
                    f"• **Số dư cũ:** `{old_balance:,}đ`\n"
                    f"• **Số dư mới:** `{user.balance:,}đ`"
                )
                asyncio.run(bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown'))
            except Exception as e:
                logger.error(f"Lỗi gửi Telegram: {e}")

            return jsonify({"success": True, "new_balance": user.balance})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== API ĐỒNG BỘ GIAO DỊCH =====
@app.route('/sync-transactions', methods=['POST'])
def sync_transactions():
    """Đồng bộ giao dịch từ local lên Render"""
    try:
        data = request.json
        transactions = data.get('transactions', [])
        
        with app.app_context():
            synced = 0
            existing = 0
            
            for t in transactions:
                # Kiểm tra đã tồn tại chưa
                existing_trans = Transaction.query.filter_by(transaction_code=t['code']).first()
                if not existing_trans:
                    user = User.query.filter_by(user_id=t['user_id']).first()
                    if user:
                        new_trans = Transaction(
                            user_id=user.id,
                            amount=t['amount'],
                            type='deposit',
                            status='pending',
                            transaction_code=t['code'],
                            description=f"Synced from local: {t['code']}",
                            created_at=datetime.now()
                        )
                        db.session.add(new_trans)
                        synced += 1
                        logger.info(f"✅ Đã đồng bộ giao dịch {t['code']}")
                    else:
                        logger.warning(f"⚠️ Không tìm thấy user {t['user_id']} cho giao dịch {t['code']}")
                else:
                    existing += 1
                    logger.info(f"⏭️ Giao dịch {t['code']} đã tồn tại")
            
            db.session.commit()
            logger.info(f"✅ Đồng bộ hoàn tất: {synced} mới, {existing} đã tồn tại")
            
            return jsonify({
                "success": True, 
                "synced": synced,
                "existing": existing,
                "total": len(transactions)
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Lỗi đồng bộ: {e}")
        return jsonify({"error": str(e)}), 500

# ===== API KIỂM TRA GIAO DỊCH =====
@app.route('/check-transaction', methods=['POST'])
def check_transaction():
    """Kiểm tra giao dịch có tồn tại không"""
    try:
        data = request.json
        code = data.get('code')
        
        with app.app_context():
            transaction = Transaction.query.filter_by(transaction_code=code).first()
            if transaction:
                user = User.query.get(transaction.user_id)
                return jsonify({
                    "exists": True,
                    "status": transaction.status,
                    "amount": transaction.amount,
                    "user_id": user.user_id if user else None
                }), 200
            return jsonify({"exists": False}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== PHẦN NÀY CHỈ CHẠY KHI FILE ĐƯỢC CHẠY TRỰC TIẾP =====
if __name__ == '__main__':
    import threading
    
    port = int(os.getenv('PORT', 8080))
    
    # Chạy Flask server trong thread riêng
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0', 
            port=port, 
            debug=False, 
            use_reloader=False,
            threaded=True
        )
    )
    flask_thread.daemon = True
    flask_thread.start()

    logger.info(f"🌐 Flask server đang chạy trên port {port}")
    logger.info("🚫 Bot Telegram ĐÃ TẮT trên Render - Chỉ chạy local")
    logger.info("📱 Để chạy bot, gõ: python bot.py ở local")

    # Giữ Flask chạy mãi - KHÔNG gọi main()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("👋 Đã dừng Flask server")