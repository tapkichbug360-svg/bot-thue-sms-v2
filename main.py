import logging
import os
import sys
import atexit
import asyncio
import time
import requests
from datetime import datetime, timedelta
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

# ===== BIẾN TOÀN CỤC CHO AUTO SYNC =====
last_sync_check = datetime.now()
processed_transactions = set()

def auto_sync_and_check():
    """Tự động đồng bộ và kiểm tra giao dịch mới mỗi 10 giây"""
    global last_sync_check, processed_transactions
    
    with app.app_context():
        try:
            # 1. KIỂM TRA GIAO DỊCH THÀNH CÔNG MỚI
            new_transactions = Transaction.query.filter(
                Transaction.status == 'success',
                Transaction.updated_at > last_sync_check
            ).all()
            
            if new_transactions:
                logger.info(f"🔍 Phát hiện {len(new_transactions)} giao dịch thành công mới")
                
                for trans in new_transactions:
                    # Tránh gửi trùng
                    if trans.id in processed_transactions:
                        continue
                        
                    user = User.query.get(trans.user_id)
                    if user and user.user_id:
                        try:
                            bot = Bot(token=os.getenv('BOT_TOKEN'))
                            message = (
                                f"💰 **NẠP TIỀN THÀNH CÔNG!**\n\n"
                                f"• **Số tiền:** `{trans.amount:,}đ`\n"
                                f"• **Mã GD:** `{trans.transaction_code}`\n"
                                f"• **Số dư mới:** `{user.balance:,}đ`\n"
                                f"• **Thời gian:** `{trans.updated_at.strftime('%H:%M:%S %d/%m/%Y')}`"
                            )
                            asyncio.run(send_telegram_message(user.user_id, message))
                            processed_transactions.add(trans.id)
                            logger.info(f"✅ Đã gửi thông báo giao dịch {trans.transaction_code}")
                        except Exception as e:
                            logger.error(f"❌ Lỗi gửi Telegram: {e}")
                
                # Giới hạn kích thước set
                if len(processed_transactions) > 1000:
                    processed_transactions = set(list(processed_transactions)[-500:])
            
            # 2. CẬP NHẬT THỜI GIAN
            last_sync_check = datetime.now()
            
        except Exception as e:
            logger.error(f"Lỗi trong auto_sync_and_check: {e}")

async def send_telegram_message(chat_id, message):
    """Gửi tin nhắn Telegram bất đồng bộ"""
    try:
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Lỗi gửi Telegram: {e}")

# ===== API NHẬN ĐỒNG BỘ TỪ LOCAL =====
@app.route('/sync-pending', methods=['POST'])
def sync_pending():
    """API nhận danh sách giao dịch pending từ local"""
    try:
        data = request.json
        transactions = data.get('transactions', [])
        
        with app.app_context():
            synced = 0
            skipped = 0
            
            for t in transactions:
                # Kiểm tra đã tồn tại chưa
                existing = Transaction.query.filter_by(transaction_code=t['code']).first()
                if not existing:
                    user = User.query.filter_by(user_id=t['user_id']).first()
                    if user:
                        new_trans = Transaction(
                            user_id=user.id,
                            amount=t['amount'],
                            type='deposit',
                            status='pending',
                            transaction_code=t['code'],
                            description=f"Auto-synced: {t['code']}",
                            created_at=datetime.now()
                        )
                        db.session.add(new_trans)
                        synced += 1
                        logger.info(f"✅ Đã đồng bộ giao dịch {t['code']} từ local")
                    else:
                        logger.warning(f"⚠️ Không tìm thấy user {t['user_id']}")
                        skipped += 1
                else:
                    skipped += 1
            
            db.session.commit()
            logger.info(f"📊 Đồng bộ hoàn tất: {synced} mới, {skipped} bỏ qua")
            
            return jsonify({
                "success": True,
                "synced": synced,
                "skipped": skipped,
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

# ===== API LẤY DANH SÁCH PENDING =====
@app.route('/get-pending', methods=['GET'])
def get_pending():
    """Lấy danh sách giao dịch pending (cho local sync)"""
    try:
        with app.app_context():
            pending = Transaction.query.filter_by(status='pending').all()
            result = []
            for trans in pending:
                user = User.query.get(trans.user_id)
                if user:
                    result.append({
                        "code": trans.transaction_code,
                        "amount": trans.amount,
                        "user_id": user.user_id,
                        "created_at": trans.created_at.isoformat() if trans.created_at else None
                    })
            
            return jsonify({
                "success": True,
                "count": len(result),
                "transactions": result
            }), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== API TEST NẠP TIỀN =====
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
                created_at=datetime.now(),
                updated_at=datetime.now()
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

# ===== THIẾT LẬP SCHEDULER =====
scheduler = BackgroundScheduler()
scheduler.start()

# Job kiểm tra số hết hạn (5 phút)
scheduler.add_job(
    func=check_expired_rentals,
    trigger=IntervalTrigger(minutes=5),
    id='check_expired_rentals',
    name='Kiểm tra số hết hạn và hoàn tiền',
    replace_existing=True
)

# Job tự động kiểm tra và đồng bộ (10 giây)
scheduler.add_job(
    func=auto_sync_and_check,
    trigger=IntervalTrigger(seconds=10),
    id='auto_sync_and_check',
    name='Tự động kiểm tra giao dịch và đồng bộ',
    replace_existing=True
)

# Dừng scheduler khi tắt app
atexit.register(lambda: scheduler.shutdown())

logger.info("⏰ SCHEDULER ĐÃ KHỞI ĐỘNG:")
logger.info("  - Kiểm tra số hết hạn: 5 phút/lần")
logger.info("  - Auto check + sync: 10 giây/lần")
logger.info("  - API sync-pending: nhận dữ liệu từ local")
logger.info("  - API check-transaction: kiểm tra giao dịch")

# ===== PHẦN CHẠY ỨNG DỤNG =====
if __name__ == '__main__':
    import threading
    
    port = int(os.getenv('PORT', 8080))
    
    # Chạy Flask server
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
    logger.info("⏱️ Auto check + sync: 10 giây/lần")

    # Giữ Flask chạy
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("👋 Đã dừng Flask server")