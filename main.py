import logging
import os
import sys
import atexit
from datetime import datetime
from flask import Flask
from database.models import db, User, Rental
from handlers.sepay import setup_sepay_webhook
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

@@app.route('/')
def home():
    return f"Bot đang chạy! MBBank: 666666291005 - NGUYEN THE LAM"

# ===== HÀM KIỂM TRA SỐ HẾT HẠN =====
def check_expired_rentals():
    """Kiểm tra và tự động hoàn tiền cho các số hết hạn"""
    with app.app_context():
        try:
            # Tìm các rental đang waiting nhưng đã hết hạn
            expired_rentals = Rental.query.filter(
                Rental.status == 'waiting',
                Rental.expires_at < datetime.now()
            ).all()
            
            for rental in expired_rentals:
                # Tìm user
                user = User.query.filter_by(user_id=rental.user_id).first()
                if user:
                    # Hoàn tiền
                    refund = rental.price_charged
                    old_balance = user.balance
                    user.balance += refund
                    
                    # Cập nhật trạng thái
                    rental.status = 'expired'
                    rental.updated_at = datetime.now()
                    
                    db.session.commit()
                    
                    logger.info(f"💰 TỰ ĐỘNG HOÀN {refund}đ CHO USER {user.user_id} (số {rental.phone_number} hết hạn)")
                    logger.info(f"   Số dư: {old_balance}đ → {user.balance}đ")
                    
                else:
                    logger.error(f"❌ Không tìm thấy user {rental.user_id} để hoàn tiền")
                    
        except Exception as e:
            logger.error(f"Lỗi kiểm tra số hết hạn: {e}")

# ===== THIẾT LẬP SCHEDULER =====
def setup_scheduler():
    """Thiết lập scheduler tự động kiểm tra số hết hạn"""
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    # Chạy mỗi 5 phút
    scheduler.add_job(
        func=check_expired_rentals,
        trigger=IntervalTrigger(minutes=5),
        id='check_expired_rentals',
        name='Kiểm tra số hết hạn và hoàn tiền',
        replace_existing=True
    )
    
    # Dừng scheduler khi tắt app
    atexit.register(lambda: scheduler.shutdown())
    
    logger.info("⏰ Scheduler kiểm tra số hết hạn đã được khởi động (5 phút/lần)")

# Gọi hàm setup_scheduler sau khi khởi tạo app
setup_scheduler()

def main():
    """Khởi chạy bot Telegram"""
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("❌ KHÔNG TÌM THẤY BOT_TOKEN trong file .env!")
        return
    
    # Tạo application
    application = Application.builder().token(token).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("rent", rent_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(rent_service_callback, pattern="^rent_service_"))
    application.add_handler(CallbackQueryHandler(rent_network_callback, pattern="^rent_network_"))
    application.add_handler(CallbackQueryHandler(rent_confirm_callback, pattern="^rent_confirm_"))
    application.add_handler(CallbackQueryHandler(rent_check_callback, pattern="^rent_check_"))
    application.add_handler(CallbackQueryHandler(rent_view_callback, pattern="^rent_view_"))
    application.add_handler(CallbackQueryHandler(rent_cancel_callback, pattern="^rent_cancel_"))
    application.add_handler(CallbackQueryHandler(rent_list_callback, pattern="^menu_rent_list$"))
    application.add_handler(CallbackQueryHandler(deposit_amount_callback, pattern="^deposit_amount_"))
    application.add_handler(CallbackQueryHandler(deposit_check_callback, pattern="^deposit_check_"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    
    # Log số lượng handlers
    handler_count = len(application.handlers.get(0, []))
    logger.info(f"✅ Đã đăng ký {handler_count} handlers")
    
    # Start bot
    logger.info("🚀 Bot đang khởi động...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    import threading
    
    # Chạy Flask server trong thread riêng
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
    
    logger.info(f"🌐 Flask server đang chạy trên port {port}")
    
    # Chạy bot Telegram
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Đã dừng bot")
    except Exception as e:
        logger.error(f"❌ Lỗi: {e}")
        import traceback
    traceback.print_exc()
def test_deposit():
    try:
        data = request.json
        user_id = data.get('user_id')
        amount = data.get('amount')
        code = data.get('code')
        
        with app.app_context():
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                return {"error": "User not found"}, 404
            
            old_balance = user.balance
            user.balance += amount
            
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                type='deposit',
                status='success',
                transaction_code=code,
                description=f"Test n�p {amount}",
                created_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"' TEST: � C�NG {amount} CHO USER {user_id}")
            return {"success": True, "new_balance": user.balance}
            
    except Exception as e:
        return {"error": str(e)}, 500


