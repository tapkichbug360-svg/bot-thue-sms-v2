import logging
import os
import sys
import atexit
import asyncio
import time
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from database.models import db, User, Rental, Transaction
from handlers.sepay import setup_sepay_webhook
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from sqlalchemy import or_
from dotenv import load_dotenv

# Telegram imports
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update

# Import t? handlers
from handlers.start import start_command, menu_command, cancel, help_command, check_command
from handlers.rent import (
    rent_command, rent_service_callback, rent_network_callback,
    rent_confirm_callback, rent_check_callback, rent_view_callback,
    rent_cancel_callback, rent_list_callback
)
from handlers.balance import balance_command
from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
from handlers.callback import menu_callback

# Load t? file .env (n?u có) - CÁCH CHU?N DUY NH?T
load_dotenv()

# Ð?c bi?n môi tru?ng, n?u không có thì báo l?i
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL')

if not BOT_TOKEN:
    print("? KHÔNG TÌM TH?Y BOT_TOKEN trong bi?n môi tru?ng ho?c file .env")
    sys.exit(1)
if not API_KEY:
    print("? KHÔNG TÌM TH?Y API_KEY")
    sys.exit(1)
if not BASE_URL:
    print("? KHÔNG TÌM TH?Y BASE_URL")
    sys.exit(1)

print(f"? BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"? API_KEY: {API_KEY[:10]}...")
print(f"? BASE_URL: {BASE_URL}")

# Múi gi? Vi?t Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    """L?y th?i gian Vi?t Nam hi?n t?i"""
    return datetime.now(VN_TZ).replace(tzinfo=None)

# T?o thu m?c database
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

# ===== C?U HÌNH LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== KH?I T?O FLASK APP =====
app = Flask(__name__)

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'bot.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    try:
        db.create_all()
        logger.info("? ÐÃ T?O DATABASE THÀNH CÔNG!")
    except Exception as e:
        if "already exists" in str(e):
            logger.info("?? Database dã t?n t?i")
        else:
            logger.error(f"L?I T?O DATABASE: {e}")

# ===== THI?T L?P WEBHOOK SEPAY =====
setup_sepay_webhook(app)

@app.route('/')
def home():
    return "Bot dang ch?y! MBBank: 666666291005 - NGUYEN THE LAM"

# ===== BI?N TOÀN C?C =====
last_check_time = get_vn_time() - timedelta(minutes=1)
processed_transactions = set()
user_cache = {}

# ===== HÀM KI?M TRA S? H?T H?N =====
def check_expired_rentals():
    """Ki?m tra và t? d?ng hoàn ti?n cho các s? h?t h?n"""
    with app.app_context():
        try:
            expired_rentals = Rental.query.filter(
                Rental.status == 'waiting',
                Rental.expires_at < get_vn_time()
            ).all()

            for rental in expired_rentals:
                user = get_or_create_user(rental.user_id)
                if user:
                    refund = rental.price_charged
                    old_balance = user.balance
                    user.balance += refund
                    rental.status = 'expired'
                    rental.updated_at = get_vn_time()
                    db.session.commit()

                    logger.info(f"?? T? Ð?NG HOÀN {refund}d CHO USER {user.user_id}")
                    
                    if BOT_TOKEN:
                        try:
                            bot = Bot(token=BOT_TOKEN)
                            message = (
                                f"? **S? H?T H?N & HOÀN TI?N**\n\n"
                                f"• **S?:** `{rental.phone_number}`\n"
                                f"• **D?ch v?:** {rental.service_name}\n"
                                f"• **Ti?n hoàn:** `{refund:,}d`\n"
                                f"• **S? du m?i:** `{user.balance:,}d`"
                            )
                            asyncio.run(send_telegram_message(user.user_id, message))
                        except Exception as e:
                            logger.error(f"L?i g?i Telegram: {e}")
        except Exception as e:
            logger.error(f"L?i ki?m tra s? h?t h?n: {e}")

# ===== HÀM GET_OR_CREATE_USER =====
def get_or_create_user(user_id, username=None):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            username=username or f"user_{user_id}",
            balance=0,
            created_at=get_vn_time(),
            last_active=get_vn_time()
        )
        db.session.add(user)
        db.session.flush()
        logger.info(f"?? ÐÃ T?O USER M?I: {user_id} - {user.username}")
    return user

# ===== API 1: KI?M TRA GIAO D?CH =====
@app.route('/api/check-transaction', methods=['POST'])
def api_check_transaction():
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

# ===== API 2: Ð?NG B? PENDING T? LOCAL =====
@app.route('/api/sync-pending', methods=['POST'])
def api_sync_pending():
    try:
        data = request.json
        transactions = data.get('transactions', [])
        
        with app.app_context():
            synced = 0
            skipped = 0
            
            for t in transactions:
                user = get_or_create_user(t['user_id'], t.get('username'))
                
                existing = Transaction.query.filter_by(transaction_code=t['code']).first()
                if not existing:
                    new_trans = Transaction(
                        user_id=user.id,
                        amount=t['amount'],
                        type='deposit',
                        status='pending',
                        transaction_code=t['code'],
                        description=f"Auto-synced: {t['code']}",
                        created_at=get_vn_time()
                    )
                    db.session.add(new_trans)
                    synced += 1
                    logger.info(f"? Ð?ng b? giao d?ch {t['code']} cho user {user.user_id}")
                else:
                    skipped += 1
            
            db.session.commit()
            
            return jsonify({
                "success": True,
                "synced": synced,
                "skipped": skipped,
                "total": len(transactions)
            }), 200
            
    except Exception as e:
        logger.error(f"? L?i d?ng b?: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 3: L?Y DANH SÁCH PENDING TRÊN RENDER =====
@app.route('/api/get-pending', methods=['GET'])
def api_get_pending():
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

# ===== API 4: KI?M TRA USER =====
@app.route('/api/check-user', methods=['POST'])
def api_check_user():
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

# ===== API 5: L?Y T?T C? GIAO D?CH C?A USER =====
@app.route('/api/user-transactions', methods=['POST'])
def api_user_transactions():
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

# ===== API 6: C?P NH?T USER =====
@app.route('/api/update-user', methods=['POST'])
def api_update_user():
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        
        with app.app_context():
            user = get_or_create_user(user_id)
            if username:
                user.username = username
                user.last_active = get_vn_time()
                db.session.commit()
                logger.info(f"?? Ðã c?p nh?t username cho user {user_id}: {username}")
            
            return jsonify({
                "success": True,
                "user_id": user.user_id,
                "username": user.username,
                "balance": user.balance
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 7: TH?NG KÊ H? TH?NG =====
@app.route('/api/stats', methods=['GET'])
def api_stats():
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
                    "timestamp": get_vn_time().isoformat()
                }
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 8: FORCE X? LÝ GIAO D?CH =====
@app.route('/api/process-transaction', methods=['POST'])
def api_process_transaction():
    try:
        data = request.json
        code = data.get('code')
        amount = data.get('amount')
        user_id = data.get('user_id')
        
        with app.app_context():
            user = get_or_create_user(user_id)
            transaction = Transaction.query.filter_by(transaction_code=code).first()
            
            if not transaction:
                transaction = Transaction(
                    user_id=user.id,
                    amount=amount,
                    type='deposit',
                    status='success',
                    transaction_code=code,
                    description=f"Force processed: {code}",
                    created_at=get_vn_time(),
                    updated_at=get_vn_time()
                )
                db.session.add(transaction)
            else:
                transaction.status = 'success'
                transaction.updated_at = get_vn_time()
            
            old_balance = user.balance
            user.balance += amount
            db.session.commit()
            
            logger.info(f"? FORCE X? LÝ: {code} - {amount}d cho user {user_id}")
            
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
    global user_cache
    try:
        user_cache = {}
        logger.info("?? Ðã reset user cache")
        return jsonify({"success": True, "message": "Cache reset"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 10: Ð?NG B? 2 CHI?U T? Ð?NG =====
@app.route('/api/sync-bidirectional', methods=['POST'])
def api_sync_bidirectional():
    try:
        data = request.json
        local_transactions = data.get('local_transactions', [])
        
        with app.app_context():
            render_pending = Transaction.query.filter_by(status='pending').all()
            render_codes = {t.transaction_code for t in render_pending}
            
            local_codes = set()
            synced_from_local = 0
            sync_to_local = []
            
            # 1. Ð?NG B? T? LOCAL LÊN RENDER
            for lt in local_transactions:
                local_codes.add(lt['code'])
                
                existing = Transaction.query.filter_by(transaction_code=lt['code']).first()
                if not existing:
                    user = get_or_create_user(lt['user_id'], lt.get('username'))
                    new_trans = Transaction(
                        user_id=user.id,
                        amount=lt['amount'],
                        type='deposit',
                        status='pending',
                        transaction_code=lt['code'],
                        description=f"Bidirectional sync: {lt['code']}",
                        created_at=get_vn_time()
                    )
                    db.session.add(new_trans)
                    synced_from_local += 1
                    logger.info(f"? Ð?ng b? t? local: {lt['code']}")
            
            # 2. CHU?N B? D? LI?U Ð?NG B? V? LOCAL
            for trans in render_pending:
                if trans.transaction_code not in local_codes:
                    user = User.query.get(trans.user_id)
                    if user:
                        sync_to_local.append({
                            "code": trans.transaction_code,
                            "amount": trans.amount,
                            "user_id": user.user_id,
                            "status": trans.status,
                            "created_at": trans.created_at.isoformat() if trans.created_at else None
                        })
            
            db.session.commit()
            
            return jsonify({
                "success": True,
                "synced_from_local": synced_from_local,
                "sync_to_local": sync_to_local,
                "render_pending_count": len(render_pending)
            }), 200
            
    except Exception as e:
        logger.error(f"? L?i sync bidirectional: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 11: FORCE Ð?NG B? USER =====
@app.route('/api/force-sync-user', methods=['POST'])
def api_force_sync_user():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        with app.app_context():
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                return jsonify({"success": False, "error": "User not found"}), 404
            
            transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).all()
            
            result = []
            for trans in transactions:
                result.append({
                    "code": trans.transaction_code,
                    "amount": trans.amount,
                    "status": trans.status,
                    "created_at": trans.created_at.isoformat() if trans.created_at else None,
                    "updated_at": trans.updated_at.isoformat() if trans.updated_at else None
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

# ===== API 12: Ð?NG B? T? Ð?NG 2 CHI?U =====
@app.route('/api/auto-sync', methods=['GET'])
def api_auto_sync():
    """API t? d?ng d?ng b? - Render t? pull d? li?u t? local (n?u local có API)"""
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
                "transactions": result,
                "timestamp": get_vn_time().isoformat()
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== HÀM T? Ð?NG KI?M TRA GIAO D?CH M?I =====
def auto_check_new_transactions():
    global last_check_time, processed_transactions
    
    with app.app_context():
        try:
            new_transactions = Transaction.query.filter(
                Transaction.status == 'success',
                Transaction.updated_at > last_check_time
            ).all()
            
            if new_transactions:
                logger.info(f"?? Phát hi?n {len(new_transactions)} giao d?ch thành công m?i")
                
                for trans in new_transactions:
                    if trans.id in processed_transactions:
                        continue
                        
                    user = User.query.get(trans.user_id)
                    if user and BOT_TOKEN:
                        try:
                            bot = Bot(token=BOT_TOKEN)
                            message = (
                                f"?? **N?P TI?N THÀNH CÔNG!**\n\n"
                                f"• **S? ti?n:** `{trans.amount:,}d`\n"
                                f"• **Mã GD:** `{trans.transaction_code}`\n"
                                f"• **S? du m?i:** `{user.balance:,}d`\n"
                                f"• **Th?i gian:** `{trans.updated_at.strftime('%H:%M:%S %d/%m/%Y')}`"
                            )
                            asyncio.run(send_telegram_message(user.user_id, message))
                            processed_transactions.add(trans.id)
                            logger.info(f"? Ðã g?i thông báo {trans.transaction_code}")
                        except Exception as e:
                            logger.error(f"? L?i g?i Telegram: {e}")
                
                if len(processed_transactions) > 1000:
                    processed_transactions = set(list(processed_transactions)[-500:])
            
            last_check_time = get_vn_time()
            
        except Exception as e:
            logger.error(f"L?i auto check: {e}")

async def send_telegram_message(chat_id, message):
    if not BOT_TOKEN:
        return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"L?i g?i Telegram: {e}")

# ===== THI?T L?P SCHEDULER =====
scheduler = BackgroundScheduler()
scheduler.start()

scheduler.add_job(
    func=check_expired_rentals,
    trigger=IntervalTrigger(minutes=5),
    id='check_expired_rentals',
    name='Ki?m tra s? h?t h?n',
    replace_existing=True
)

scheduler.add_job(
    func=auto_check_new_transactions,
    trigger=IntervalTrigger(seconds=10),
    id='auto_check_new_transactions',
    name='Ki?m tra giao d?ch m?i',
    replace_existing=True
)

atexit.register(lambda: scheduler.shutdown())

logger.info("="*60)
logger.info("?? H? TH?NG ÐÃ KH?I Ð?NG V?I 12 API:")
logger.info("  1. POST /api/check-transaction - Ki?m tra giao d?ch")
logger.info("  2. POST /api/sync-pending - Ð?ng b? pending t? local")
logger.info("  3. GET  /api/get-pending - L?y pending trên Render")
logger.info("  4. POST /api/check-user - Ki?m tra/t?o user")
logger.info("  5. POST /api/user-transactions - L?ch s? giao d?ch user")
logger.info("  6. POST /api/update-user - C?p nh?t user")
logger.info("  7. GET  /api/stats - Th?ng kê h? th?ng")
logger.info("  8. POST /api/process-transaction - Force x? lý giao d?ch")
logger.info("  9. POST /api/reset-cache - Reset cache")
logger.info(" 10. POST /api/sync-bidirectional - Ð?ng b? 2 chi?u")
logger.info(" 11. POST /api/force-sync-user - Force d?ng b? user")
logger.info(" 12. GET  /api/auto-sync - Ð?ng b? t? d?ng")
logger.info("="*60)
logger.info("??  Auto check giao d?ch m?i: 10 giây/l?n")
logger.info("??  Auto check s? h?t h?n: 5 phút/l?n")
logger.info("="*60)

if __name__ == '__main__':
    import threading
    
    port = int(os.getenv('PORT', 8080))
    
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

    logger.info(f"?? Flask server dang ch?y trên port {port}")
    logger.info("?? Bot Telegram ÐÃ T?T trên Render - Ch? ch?y local")
    logger.info("?? Ð? ch?y bot, gõ: python bot.py ? local")
    logger.info("?? L?nh ki?m tra giao d?ch: /check MÃ_GD")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("?? Ðã d?ng Flask server")
