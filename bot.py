import logging
import os
import sys
import asyncio
import signal
import psutil
import requests
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from flask import Flask
from database.models import db, User, Transaction

# === CÁCH ĐƠN GIẢN NHẤT - ĐỌC TRỰC TIẾP FILE ===
BOT_TOKEN = None

# Đọc trực tiếp file .env
if os.path.exists('.env'):
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('BOT_TOKEN='):
                BOT_TOKEN = line.split('=')[1].strip()
                print(f"✅ Đã đọc BOT_TOKEN từ file: {BOT_TOKEN[:10]}...")
                break

if not BOT_TOKEN:
    print("❌ KHÔNG TÌM THẤY BOT_TOKEN trong file .env")
    print("📁 Nội dung file .env:")
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            print(f.read())
    sys.exit(1)

# Cấu hình logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === DATABASE ===
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'database', 'bot.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
logger.info(f"✅ Database path: {db_path}")

# Import handlers
try:
    from handlers.start import start_command
    from handlers.balance import balance_command
    from handlers.deposit import deposit_command, deposit_amount_callback, deposit_check_callback
    from handlers.rent import (
        rent_command, rent_service_callback, rent_network_callback,
        rent_confirm_callback, rent_check_callback, rent_cancel_callback,
        rent_view_callback
    )
    from handlers.callback import menu_callback
    logger.info("✅ Import handlers thành công")
except Exception as e:
    logger.error(f"❌ LỖI IMPORT HANDLERS: {e}")
    sys.exit(1)

def kill_other_instances():
    current_pid = os.getpid()
    killed = 0
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if (proc.info['pid'] != current_pid and 
                    'python' in proc.info['name'] and 
                    'bot.py' in cmdline):
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    killed += 1
                    logger.info(f"✅ Đã kill instance cũ PID: {proc.info['pid']}")
            except:
                pass
    except Exception as e:
        logger.error(f"Lỗi kill: {e}")
    return killed

def cleanup_telegram():
    try:
        close_url = f"https://api.telegram.org/bot{BOT_TOKEN}/close"
        close_res = requests.post(close_url)
        logger.info(f"Close connection: {close_res.status_code}")
        
        webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        webhook_res = requests.post(webhook_url)
        logger.info(f"Delete webhook: {webhook_res.status_code}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

async def main():
    killed = kill_other_instances()
    if killed > 0:
        logger.info(f"Đã kill {killed} instance cũ")
    cleanup_telegram()
    
    try:
        logger.info("🚀 BOT ĐANG KHỞI ĐỘNG...")
        
        with app.app_context():
            try:
                user_count = User.query.count()
                logger.info(f"✅ Kết nối database thành công! Số user: {user_count}")
            except Exception as e:
                logger.error(f"❌ Lỗi kết nối database: {e}")
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("deposit", deposit_command))
        application.add_handler(CommandHandler("rent", rent_command))
        
        application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
        application.add_handler(CallbackQueryHandler(deposit_amount_callback, pattern="^deposit_amount_"))
        application.add_handler(CallbackQueryHandler(deposit_check_callback, pattern="^deposit_check_"))
        application.add_handler(CallbackQueryHandler(rent_service_callback, pattern="^rent_service_"))
        application.add_handler(CallbackQueryHandler(rent_network_callback, pattern="^rent_network_"))
        application.add_handler(CallbackQueryHandler(rent_confirm_callback, pattern="^rent_confirm_"))
        application.add_handler(CallbackQueryHandler(rent_check_callback, pattern="^rent_check_"))
        application.add_handler(CallbackQueryHandler(rent_cancel_callback, pattern="^rent_cancel_"))
        application.add_handler(CallbackQueryHandler(rent_view_callback, pattern="^rent_view_"))
        
        logger.info("✅ BOT KHỞI ĐỘNG THÀNH CÔNG!")
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"❌ LỖI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot đã dừng")
    except Exception as e:
        logger.error(f"❌ LỖI: {e}")
