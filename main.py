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

# Import tá»« handlers
from handlers.start import start_command, menu_command, cancel, help_command, check_command
from handlers.rent import (
    rent_command, rent_service_callback, rent_network_callback,
    rent_confirm_callback, rent_check_callback, rent_view_callback,
    rent_cancel_callback, rent_list_callback
)
from handlers.balance import balance_command
from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
from handlers.callback import menu_callback

# Táº¡o thÆ° má»¥c database
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

# ===== Äá»ŒC FILE .ENV - CHUáº¨N CHO Cáº¢ LOCAL VÃ€ RENDER =====
print("ðŸ”§ KIá»‚M TRA Cáº¤U HÃŒNH MÃ”I TRÆ¯á»œNG...")
print("="*50)

if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip()
                    print(f"âœ… ÄÃ£ Ä‘á»c tá»« .env: {key}")
        print("ðŸ“¦ DÃ¹ng cáº¥u hÃ¬nh tá»« file .env (local mode)")
    except Exception as e:
        print(f"âš ï¸ Lá»—i Ä‘á»c .env: {e}")
        print("â˜ï¸ Chuyá»ƒn sang dÃ¹ng biáº¿n mÃ´i trÆ°á»ng Render")
else:
    print("â˜ï¸ KhÃ´ng tÃ¬m tháº¥y file .env, dÃ¹ng biáº¿n mÃ´i trÆ°á»ng Render")

required_vars = ['BOT_TOKEN', 'MB_ACCOUNT', 'MB_NAME', 'MB_BIN', 'SEPAY_TOKEN']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"âš ï¸ THIáº¾U BIáº¾N MÃ”I TRÆ¯á»œNG: {missing_vars}")
else:
    print("âœ… Táº¥t cáº£ biáº¿n mÃ´i trÆ°á»ng Ä‘Ã£ sáºµn sÃ ng")

print("="*50)

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
        logger.info("âœ… ÄÃƒ Táº O DATABASE THÃ€NH CÃ”NG!")
    except Exception as e:
        if "already exists" in str(e):
            logger.info("â„¹ï¸ Database Ä‘Ã£ tá»“n táº¡i")
        else:
            logger.error(f"Lá»–I Táº O DATABASE: {e}")

setup_sepay_webhook(app)

@app.route('/')
def home():
    return "Bot Ä‘ang cháº¡y! MBBank: 666666291005 - NGUYEN THE LAM"

# ===== BIáº¾N TOÃ€N Cá»¤C =====
last_check_time = datetime.now() - timedelta(minutes=1)
processed_transactions = set()
user_cache = {}
# ===== HÃ€M KIá»‚M TRA Sá» Háº¾T Háº N =====
def check_expired_rentals():
    """Kiá»ƒm tra vÃ  tá»± Ä‘á»™ng hoÃ n tiá»n cho cÃ¡c sá»‘ háº¿t háº¡n"""
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

                    logger.info(f"ðŸ’° Tá»° Äá»˜NG HOÃ€N {refund}Ä‘ CHO USER {user.user_id}")
                    
                    if os.getenv('BOT_TOKEN'):
                        try:
                            bot = Bot(token=os.getenv('BOT_TOKEN'))
                            message = (
                                f"â° **Sá» Háº¾T Háº N & HOÃ€N TIá»€N**\n\n"
                                f"â€¢ **Sá»‘:** `{rental.phone_number}`\n"
                                f"â€¢ **Dá»‹ch vá»¥:** {rental.service_name}\n"
                                f"â€¢ **Tiá»n hoÃ n:** `{refund:,}Ä‘`\n"
                                f"â€¢ **Sá»‘ dÆ° má»›i:** `{user.balance:,}Ä‘`"
                            )
                            asyncio.run(send_telegram_message(user.user_id, message))
                        except Exception as e:
                            logger.error(f"Lá»—i gá»­i Telegram: {e}")
        except Exception as e:
            logger.error(f"Lá»—i kiá»ƒm tra sá»‘ háº¿t háº¡n: {e}")

# ===== HÃ€M GET_OR_CREATE_USER =====
def get_or_create_user(user_id, username=None):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            username=username or f"user_{user_id}",
            balance=0,
            created_at=datetime.now(),
            last_active=datetime.now()
        )
        db.session.add(user)
        db.session.flush()
        logger.info(f"ðŸ†• ÄÃƒ Táº O USER Má»šI: {user_id} - {user.username}")
    return user

# ===== API 1: KIá»‚M TRA GIAO Dá»ŠCH =====
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

# ===== API 2: Äá»’NG Bá»˜ PENDING Tá»ª LOCAL =====
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
                        created_at=datetime.now()
                    )
                    db.session.add(new_trans)
                    synced += 1
                    logger.info(f"âœ… Äá»“ng bá»™ giao dá»‹ch {t['code']} cho user {user.user_id}")
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
        logger.error(f"âŒ Lá»—i Ä‘á»“ng bá»™: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 3: Láº¤Y DANH SÃCH PENDING TRÃŠN RENDER =====
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

# ===== API 4: KIá»‚M TRA USER =====
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

# ===== API 5: Láº¤Y Táº¤T Cáº¢ GIAO Dá»ŠCH Cá»¦A USER =====
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

# ===== API 6: Cáº¬P NHáº¬T USER =====
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
                user.last_active = datetime.now()
                db.session.commit()
                logger.info(f"ðŸ“ ÄÃ£ cáº­p nháº­t username cho user {user_id}: {username}")
            
            return jsonify({
                "success": True,
                "user_id": user.user_id,
                "username": user.username,
                "balance": user.balance
            }), 200
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 7: THá»NG KÃŠ Há»† THá»NG =====
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
                    "timestamp": datetime.now().isoformat()
                }
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 8: FORCE Xá»¬ LÃ GIAO Dá»ŠCH =====
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
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(transaction)
            else:
                transaction.status = 'success'
                transaction.updated_at = datetime.now()
            
            old_balance = user.balance
            user.balance += amount
            db.session.commit()
            
            logger.info(f"âš¡ FORCE Xá»¬ LÃ: {code} - {amount}Ä‘ cho user {user_id}")
            
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
        logger.info("ðŸ”„ ÄÃ£ reset user cache")
        return jsonify({"success": True, "message": "Cache reset"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 10: Äá»’NG Bá»˜ 2 CHIá»€U Tá»° Äá»˜NG =====
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
            
            # 1. Äá»’NG Bá»˜ Tá»ª LOCAL LÃŠN RENDER
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
                        created_at=datetime.now()
                    )
                    db.session.add(new_trans)
                    synced_from_local += 1
                    logger.info(f"âœ… Äá»“ng bá»™ tá»« local: {lt['code']}")
            
            # 2. CHUáº¨N Bá»Š Dá»® LIá»†U Äá»’NG Bá»˜ Vá»€ LOCAL
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
        logger.error(f"âŒ Lá»—i sync bidirectional: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== API 11: FORCE Äá»’NG Bá»˜ USER =====
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

# ===== API 12: Äá»’NG Bá»˜ Tá»° Äá»˜NG 2 CHIá»€U (KHÃ”NG Cáº¦N LOCAL Gá»¬I) =====
@app.route('/api/auto-sync', methods=['GET'])
def api_auto_sync():
    """API tá»± Ä‘á»™ng Ä‘á»“ng bá»™ - Render tá»± pull dá»¯ liá»‡u tá»« local (náº¿u local cÃ³ API)"""
    try:
        # ÄÃ¢y lÃ  API Ä‘á»ƒ local gá»i Ä‘áº¿n, khÃ´ng pháº£i Render tá»± gá»i
        # Local sáº½ gá»i API nÃ y Ä‘á»ƒ láº¥y pending tá»« Render
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
                "timestamp": datetime.now().isoformat()
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== HÃ€M Tá»° Äá»˜NG KIá»‚M TRA GIAO Dá»ŠCH Má»šI =====
def auto_check_new_transactions():
    global last_check_time, processed_transactions
    
    with app.app_context():
        try:
            new_transactions = Transaction.query.filter(
                Transaction.status == 'success',
                Transaction.updated_at > last_check_time
            ).all()
            
            if new_transactions:
                logger.info(f"ðŸ” PhÃ¡t hiá»‡n {len(new_transactions)} giao dá»‹ch thÃ nh cÃ´ng má»›i")
                
                for trans in new_transactions:
                    if trans.id in processed_transactions:
                        continue
                        
                    user = User.query.get(trans.user_id)
                    if user and os.getenv('BOT_TOKEN'):
                        try:
                            bot = Bot(token=os.getenv('BOT_TOKEN'))
                            message = (
                                f"ðŸ’° **Náº P TIá»€N THÃ€NH CÃ”NG!**\n\n"
                                f"â€¢ **Sá»‘ tiá»n:** `{trans.amount:,}Ä‘`\n"
                                f"â€¢ **MÃ£ GD:** `{trans.transaction_code}`\n"
                                f"â€¢ **Sá»‘ dÆ° má»›i:** `{user.balance:,}Ä‘`\n"
                                f"â€¢ **Thá»i gian:** `{trans.updated_at.strftime('%H:%M:%S %d/%m/%Y')}`"
                            )
                            asyncio.run(send_telegram_message(user.user_id, message))
                            processed_transactions.add(trans.id)
                            logger.info(f"âœ… ÄÃ£ gá»­i thÃ´ng bÃ¡o {trans.transaction_code}")
                        except Exception as e:
                            logger.error(f"âŒ Lá»—i gá»­i Telegram: {e}")
                
                if len(processed_transactions) > 1000:
                    processed_transactions = set(list(processed_transactions)[-500:])
            
            last_check_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Lá»—i auto check: {e}")

async def send_telegram_message(chat_id, message):
    if not os.getenv('BOT_TOKEN'):
        return
    try:
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Lá»—i gá»­i Telegram: {e}")

# ===== THIáº¾T Láº¬P SCHEDULER =====
scheduler = BackgroundScheduler()
scheduler.start()

scheduler.add_job(
    func=check_expired_rentals,
    trigger=IntervalTrigger(minutes=5),
    id='check_expired_rentals',
    name='Kiá»ƒm tra sá»‘ háº¿t háº¡n',
    replace_existing=True
)

scheduler.add_job(
    func=auto_check_new_transactions,
    trigger=IntervalTrigger(seconds=10),
    id='auto_check_new_transactions',
    name='Kiá»ƒm tra giao dá»‹ch má»›i',
    replace_existing=True
)

atexit.register(lambda: scheduler.shutdown())

logger.info("="*60)
logger.info("ðŸš€ Há»† THá»NG ÄÃƒ KHá»žI Äá»˜NG Vá»šI 12 API:")
logger.info("  1. POST /api/check-transaction - Kiá»ƒm tra giao dá»‹ch")
logger.info("  2. POST /api/sync-pending - Äá»“ng bá»™ pending tá»« local")
logger.info("  3. GET  /api/get-pending - Láº¥y pending trÃªn Render")
logger.info("  4. POST /api/check-user - Kiá»ƒm tra/táº¡o user")
logger.info("  5. POST /api/user-transactions - Lá»‹ch sá»­ giao dá»‹ch user")
logger.info("  6. POST /api/update-user - Cáº­p nháº­t user")
logger.info("  7. GET  /api/stats - Thá»‘ng kÃª há»‡ thá»‘ng")
logger.info("  8. POST /api/process-transaction - Force xá»­ lÃ½ giao dá»‹ch")
logger.info("  9. POST /api/reset-cache - Reset cache")
logger.info(" 10. POST /api/sync-bidirectional - Äá»“ng bá»™ 2 chiá»u")
logger.info(" 11. POST /api/force-sync-user - Force Ä‘á»“ng bá»™ user")
logger.info(" 12. GET  /api/auto-sync - Äá»“ng bá»™ tá»± Ä‘á»™ng")
logger.info("="*60)
logger.info("â±ï¸  Auto check giao dá»‹ch má»›i: 10 giÃ¢y/láº§n")
logger.info("â±ï¸  Auto check sá»‘ háº¿t háº¡n: 5 phÃºt/láº§n")
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

    logger.info(f"ðŸŒ Flask server Ä‘ang cháº¡y trÃªn port {port}")
    logger.info("ðŸš« Bot Telegram ÄÃƒ Táº®T trÃªn Render - Chá»‰ cháº¡y local")
    logger.info("ðŸ“± Äá»ƒ cháº¡y bot, gÃµ: python bot.py á»Ÿ local")
    logger.info("ðŸ“ Lá»‡nh kiá»ƒm tra giao dá»‹ch: /check MÃƒ_GD")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("ðŸ‘‹ ÄÃ£ dá»«ng Flask server")