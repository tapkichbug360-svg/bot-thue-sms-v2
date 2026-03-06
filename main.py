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
from sqlalchemy import or_

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

# ===== BIẾN TOÀN CỤC =====
last_check_time = datetime.now() - timedelta(minutes=1)
processed_transactions = set()
user_cache = {}

# ===== HÀM KIỂM TRA USER TỰ ĐỘNG =====
def get_or_create_user(user_id, username=None):
    """Lấy user từ cache/db, tự động tạo nếu chưa có"""
    global user_cache
    
    # Kiểm tra cache
    if user_id in user_cache:
        return user_cache[user_id]
    
    # Tìm trong database
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        # Tạo user mới
        user = User(
            user_id=user_id,
            username=username or f"user_{user_id}",
            balance=0,
            created_at=datetime.now(),
            last_active=datetime.now()
        )
        db.session.add(user)
        db.session.commit()
        logger.info(f"🆕 ĐÃ TẠO USER MỚI: {user_id} - {user.username}")
    
    # Lưu vào cache
    user_cache[user_id] = user
    return user

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
                user = get_or_create_user(rental.user_id)
                if user:
                    refund = rental.price_charged
                    old_balance = user.balance
                    user.balance += refund
                    rental.status = 'expired'
                    rental.updated_at = datetime.now()
                    db.session.commit()

                    logger.info(f"💰 TỰ ĐỘNG HOÀN {refund}đ CHO USER {user.user_id}")
                    
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
                        asyncio.run(send_telegram_message(user.user_id, message))
                    except Exception as e:
                        logger.error(f"Lỗi gửi Telegram: {e}")
        except Exception as e:
            logger.error(f"Lỗi kiểm tra số hết hạn: {e}")

# ===== API 1: KIỂM TRA GIAO DỊCH =====
@app.route('/api/check-transaction', methods=['POST'])
def api_check_transaction():
    """Kiểm tra thông tin giao dịch"""
    try:
        data = request.json
        code = data.get('code')
        
        with app.app_context():
            transaction = Transaction.query.filter_by(transaction_code=code).first()
            if transaction:
                user = User.query.get(transaction.user_id)
                return jsonify({
                    "success": True,
                    "exists": True,
                    "status": transaction.status,
                    "amount": transaction.amount,
                    "user_id": user.user_id if user else None,
                    "created_at": transaction.created_at.isoformat() if transaction.created_at else None
                }), 200
            return jsonify({
                "success": True,
                "exists": False,
                "message": "Transaction not found"
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 2: ĐỒNG BỘ PENDING TỪ LOCAL =====
@app.route('/api/sync-pending', methods=['POST'])
def api_sync_pending():
    """Đồng bộ danh sách giao dịch pending từ local"""
    try:
        data = request.json
        transactions = data.get('transactions', [])
        
        with app.app_context():
            synced = 0
            skipped = 0
            new_users = 0
            
            for t in transactions:
                # Tự động tạo user nếu chưa có
                user = get_or_create_user(t['user_id'])
                
                # Kiểm tra giao dịch đã tồn tại chưa
                existing = Transaction.query.filter_by(transaction_code=t['code']).first()
                if not existing:
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
                    logger.info(f"✅ Đồng bộ giao dịch {t['code']} cho user {user.user_id}")
                else:
                    skipped += 1
            
            db.session.commit()
            logger.info(f"📊 Đồng bộ: {synced} mới, {skipped} cũ, {new_users} user mới")
            
            return jsonify({
                "success": True,
                "synced": synced,
                "skipped": skipped,
                "new_users": new_users,
                "total": len(transactions)
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Lỗi đồng bộ: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 3: LẤY DANH SÁCH PENDING TRÊN RENDER =====
@app.route('/api/get-pending', methods=['GET'])
def api_get_pending():
    """Lấy danh sách giao dịch pending trên Render"""
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
                        "status": trans.status,
                        "created_at": trans.created_at.isoformat() if trans.created_at else None
                    })
            
            return jsonify({
                "success": True,
                "count": len(result),
                "transactions": result
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 4: KIỂM TRA USER =====
@app.route('/api/check-user', methods=['POST'])
def api_check_user():
    """Kiểm tra thông tin user, tự động tạo nếu chưa có"""
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username', f"user_{user_id}")
        
        with app.app_context():
            user = get_or_create_user(user_id, username)
            
            return jsonify({
                "success": True,
                "exists": True,
                "user_id": user.user_id,
                "username": user.username,
                "balance": user.balance,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 5: LẤY TẤT CẢ GIAO DỊCH CỦA USER =====
@app.route('/api/user-transactions', methods=['POST'])
def api_user_transactions():
    """Lấy lịch sử giao dịch của user"""
    try:
        data = request.json
        user_id = data.get('user_id')
        limit = data.get('limit', 10)
        
        with app.app_context():
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                return jsonify({
                    "success": True,
                    "exists": False,
                    "message": "User not found"
                }), 200
            
            transactions = Transaction.query.filter_by(user_id=user.id).order_by(
                Transaction.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for trans in transactions:
                result.append({
                    "code": trans.transaction_code,
                    "amount": trans.amount,
                    "type": trans.type,
                    "status": trans.status,
                    "created_at": trans.created_at.isoformat() if trans.created_at else None
                })
            
            return jsonify({
                "success": True,
                "user_id": user.user_id,
                "username": user.username,
                "balance": user.balance,
                "transactions": result
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 6: CẬP NHẬT USER =====
@app.route('/api/update-user', methods=['POST'])
def api_update_user():
    """Cập nhật thông tin user"""
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        
        with app.app_context():
            user = get_or_create_user(user_id)
            if username:
                user.username = username
                user.last_active = datetime.now()
                db.session.commit()
                logger.info(f"📝 Đã cập nhật username cho user {user_id}: {username}")
            
            return jsonify({
                "success": True,
                "user_id": user.user_id,
                "username": user.username,
                "balance": user.balance
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 7: THỐNG KÊ HỆ THỐNG =====
@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Thống kê tổng quan hệ thống"""
    try:
        with app.app_context():
            total_users = User.query.count()
            total_transactions = Transaction.query.count()
            pending_transactions = Transaction.query.filter_by(status='pending').count()
            success_transactions = Transaction.query.filter_by(status='success').count()
            total_deposits = db.session.query(db.func.sum(Transaction.amount)).filter(
                Transaction.status == 'success'
            ).scalar() or 0
            
            return jsonify({
                "success": True,
                "stats": {
                    "total_users": total_users,
                    "total_transactions": total_transactions,
                    "pending_transactions": pending_transactions,
                    "success_transactions": success_transactions,
                    "total_deposits": total_deposits,
                    "timestamp": datetime.now().isoformat()
                }
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 8: FORCE XỬ LÝ GIAO DỊCH =====
@app.route('/api/process-transaction', methods=['POST'])
def api_process_transaction():
    """Force xử lý giao dịch (dùng khi webhook lỗi)"""
    try:
        data = request.json
        code = data.get('code')
        amount = data.get('amount')
        user_id = data.get('user_id')
        
        with app.app_context():
            user = get_or_create_user(user_id)
            transaction = Transaction.query.filter_by(transaction_code=code).first()
            
            if not transaction:
                # Tạo giao dịch mới
                transaction = Transaction(
                    user_id=user.id,
                    amount=amount,
                    type='deposit',
                    status='success',
                    transaction_code=code,
                    description=f"Force processed: {code}",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(transaction)
            else:
                # Cập nhật giao dịch cũ
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
            
            # Cộng tiền
            old_balance = user.balance
            user.balance += amount
            db.session.commit()
            
            logger.info(f"⚡ FORCE XỬ LÝ: {code} - {amount}đ cho user {user_id}")
            
            return jsonify({
                "success": True,
                "code": code,
                "amount": amount,
                "old_balance": old_balance,
                "new_balance": user.balance
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 9: RESET CACHE =====
@app.route('/api/reset-cache', methods=['POST'])
def api_reset_cache():
    """Reset cache user (dùng khi debug)"""
    global user_cache
    try:
        user_cache = {}
        logger.info("🔄 Đã reset user cache")
        return jsonify({"success": True, "message": "Cache reset"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== HÀM TỰ ĐỘNG KIỂM TRA GIAO DỊCH MỚI =====
def auto_check_new_transactions():
    """Tự động kiểm tra giao dịch thành công mới mỗi 10 giây"""
    global last_check_time, processed_transactions
    
    with app.app_context():
        try:
            # Tìm giao dịch success từ sau lần check trước
            new_transactions = Transaction.query.filter(
                Transaction.status == 'success',
                Transaction.updated_at > last_check_time
            ).all()
            
            if new_transactions:
                logger.info(f"🔍 Phát hiện {len(new_transactions)} giao dịch thành công mới")
                
                for trans in new_transactions:
                    if trans.id in processed_transactions:
                        continue
                        
                    user = User.query.get(trans.user_id)
                    if user:
                        # Gửi thông báo Telegram
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
                            logger.info(f"✅ Đã gửi thông báo {trans.transaction_code}")
                        except Exception as e:
                            logger.error(f"❌ Lỗi gửi Telegram: {e}")
                
                # Giới hạn kích thước cache
                if len(processed_transactions) > 1000:
                    processed_transactions = set(list(processed_transactions)[-500:])
            
            last_check_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Lỗi auto check: {e}")

async def send_telegram_message(chat_id, message):
    """Gửi tin nhắn Telegram bất đồng bộ"""
    try:
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Lỗi gửi Telegram: {e}")

# ===== THIẾT LẬP SCHEDULER =====
scheduler = BackgroundScheduler()
scheduler.start()

# Job kiểm tra số hết hạn (5 phút)
scheduler.add_job(
    func=check_expired_rentals,
    trigger=IntervalTrigger(minutes=5),
    id='check_expired_rentals',
    name='Kiểm tra số hết hạn',
    replace_existing=True
)

# Job tự động kiểm tra giao dịch mới (10 giây)
scheduler.add_job(
    func=auto_check_new_transactions,
    trigger=IntervalTrigger(seconds=10),
    id='auto_check_new_transactions',
    name='Kiểm tra giao dịch mới',
    replace_existing=True
)

# Dừng scheduler khi tắt app
atexit.register(lambda: scheduler.shutdown())

logger.info("="*60)
logger.info("🚀 HỆ THỐNG ĐÃ KHỞI ĐỘNG VỚI CÁC API:")
logger.info("  📌 POST /api/check-transaction - Kiểm tra giao dịch")
logger.info("  📌 POST /api/sync-pending - Đồng bộ pending từ local")
logger.info("  📌 GET  /api/get-pending - Lấy pending trên Render")
logger.info("  📌 POST /api/check-user - Kiểm tra/tạo user")
logger.info("  📌 POST /api/user-transactions - Lịch sử giao dịch user")
logger.info("  📌 POST /api/update-user - Cập nhật user")
logger.info("  📌 GET  /api/stats - Thống kê hệ thống")
logger.info("  📌 POST /api/process-transaction - Force xử lý giao dịch")
logger.info("  📌 POST /api/reset-cache - Reset cache")
logger.info("="*60)
logger.info("⏱️  Auto check giao dịch mới: 10 giây/lần")
logger.info("⏱️  Auto check số hết hạn: 5 phút/lần")
logger.info("="*60)

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

    # Giữ Flask chạy
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("👋 Đã dừng Flask server")