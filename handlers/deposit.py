from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from bot import app
from database.models import User, Transaction, db
from bot import app
from datetime import datetime
import logging
import random
import string
import os
import asyncio
import requests
import urllib.parse
from bot import app

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')
MB_BIN = os.getenv('MB_BIN', '970422')
RENDER_URL = os.getenv('RENDER_URL', 'https://bot-thue-sms-v2.onrender.com')

# Cache d? tránh push trùng
pushed_transactions = set()

async def push_user_to_render(user_id, username):
    """Ð?y user lên Render ngay l?p t?c"""
    try:
        response = requests.post(
            f"{RENDER_URL}/api/check-user",
            json={'user_id': user_id, 'username': username},
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"? Ðã push user {user_id} lên Render thành công")
            return True
        else:
            logger.warning(f"?? Push user {user_id} th?t b?i: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"? L?i push user {user_id}: {e}")
        return False

async def push_transaction_to_render(transaction_code, amount, user_id, username):
    """Ð?y giao d?ch lên Render ngay sau khi t?o"""
    global pushed_transactions
    
    # Tránh push trùng
    if transaction_code in pushed_transactions:
        logger.info(f"?? Giao d?ch {transaction_code} dã du?c push tru?c dó")
        return True
    
    try:
        response = requests.post(
            f"{RENDER_URL}/api/sync-pending",
            json={
                'transactions': [{
                    'code': transaction_code,
                    'amount': amount,
                    'user_id': user_id,
                    'username': username
                }]
            },
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"? Ðã d?y giao d?ch {transaction_code} lên Render thành công: {result}")
            pushed_transactions.add(transaction_code)
            
            # Gi?i h?n kích thu?c cache
            if len(pushed_transactions) > 100:
                pushed_transactions.clear()
            
            return True
        else:
            logger.warning(f"?? Ð?y giao d?ch {transaction_code} th?t b?i: {response.status_code}")
            try:
                error_detail = response.json()
                logger.error(f"?? Chi ti?t l?i: {error_detail}")
            except:
                pass
            return False
    except requests.exceptions.Timeout:
        logger.error(f"? Timeout khi d?y giao d?ch {transaction_code}")
        return False
    except Exception as e:
        logger.error(f"? L?i d?y giao d?ch {transaction_code}: {e}")
        return False

async def deposit_command(update: Update, context: Context):
    """Hi?n th? menu n?p ti?n"""
    transaction_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data['pending_deposit'] = {'code': transaction_code, 'amount': None}
    
    amounts = [20000, 50000, 100000, 200000, 500000, 1000000]
    keyboard = []
    row = []
    for i, amount in enumerate(amounts):
        btn = InlineKeyboardButton(f"{amount:,}d", callback_data=f"deposit_amount_{amount}")
        row.append(btn)
        if len(row) == 2 or i == len(amounts)-1:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("?? Quay l?i menu chính", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""?? **N?P TI?N QUA MBBANK**

?? **S? TK:** `{MB_ACCOUNT}`
?? **Ch? TK:** {MB_NAME}
?? **Ngân hàng:** MBBank

?? **N?i dung:** NAP {transaction_code}

?? **Ch?n s? ti?n:**"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def deposit_amount_callback(update: Update, context: Context):
    """X? lý khi ch?n s? ti?n"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    try:
        amount = int(query.data.split('_')[2])
        pending = context.user_data.get('pending_deposit', {})
        transaction_code = pending.get('code')
        
        if not transaction_code:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="? Có l?i x?y ra! Vui lòng th? l?i."
            )
            return
        
        user = update.effective_user
        username = user.username or user.first_name or f"user_{user.id}"
        
        # Luu giao d?ch vào database local
        from main import app
from bot import app
        with app.app_context():
            # Tìm ho?c t?o user
            db_user = User.query.filter_by(user_id=user.id).first()
            if not db_user:
                db_user = User(
                    user_id=user.id,
                    username=username,
                    balance=0,
                    created_at=datetime.now()
                )
                db.session.add(db_user)
                db.session.commit()
                logger.info(f"? Ðã t?o user m?i: {user.id}")
            
            # T?o transaction pending
            transaction = Transaction(
                user_id=db_user.id,
                amount=amount,
                type='deposit',
                status='pending',
                transaction_code=transaction_code,
                description=f'N?p {amount}d qua MBBank',
                created_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"? ÐÃ T?O GIAO D?CH: {transaction_code} - {amount}d cho user {user.id}")
        
        # === T? Ð?NG Ð?Y LÊN RENDER NGAY L?P T?C ===
        await asyncio.gather(
            push_user_to_render(user.id, username),
            push_transaction_to_render(transaction_code, amount, user.id, username)
        )
        
        # T?o QR code
        content = f"NAP {transaction_code}"
        encoded_content = urllib.parse.quote(content)
        qr_url = f"https://img.vietqr.io/image/{MB_BIN}-{MB_ACCOUNT}-compact2.jpg?amount={amount}&addInfo={encoded_content}&accountName={MB_NAME}"
        
        keyboard = [
            [InlineKeyboardButton("? TÔI ÐÃ CHUY?N KHO?N", callback_data=f"deposit_check_{transaction_code}")],
            [InlineKeyboardButton("?? N?p s? khác", callback_data="menu_deposit")],
            [InlineKeyboardButton("?? Thuê s?", callback_data="menu_rent")],
            [InlineKeyboardButton("?? Menu chính", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=qr_url,
            caption=f"""?? **THÔNG TIN CHUY?N KHO?N**

?? **STK:** `{MB_ACCOUNT}`
?? **Ch? TK:** {MB_NAME}
?? **S? ti?n:** {amount:,}d
?? **N?i dung:** `{content}`

? **B?m nút 'TÔI ÐÃ CHUY?N KHO?N' sau khi chuy?n!""",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        await query.delete_message()
        
    except Exception as e:
        logger.error(f"L?i deposit_amount_callback: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="? Có l?i x?y ra! Vui lòng th? l?i."
        )

async def deposit_check_callback(update: Update, context: Context):
    """X? lý khi user b?m 'TÔI ÐÃ CHUY?N KHO?N'"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    try:
        transaction_code = query.data.split('_')[2]
        logger.info(f"?? User báo dã chuy?n kho?n - Mã GD: {transaction_code}")
        
        from main import app
from bot import app
        with app.app_context():
            transaction = Transaction.query.filter_by(
                transaction_code=transaction_code, 
                status='pending'
            ).first()
            
            if not transaction:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"? **KHÔNG TÌM TH?Y GIAO D?CH**\n\nMã GD: {transaction_code}\nVui lòng th? l?i ho?c liên h? admin.",
                    parse_mode='Markdown'
                )
                return
            
            # C?p nh?t th?i gian
            transaction.updated_at = datetime.now()
            db.session.commit()
            
            # L?y user d? push l?i (phòng tru?ng h?p)
            user = User.query.get(transaction.user_id)
            if user:
                # Push l?i user và transaction d? d?m b?o
                await asyncio.gather(
                    push_user_to_render(user.user_id, user.username or f"user_{user.user_id}"),
                    push_transaction_to_render(transaction_code, transaction.amount, user.user_id, user.username)
                )
            
            # G?I THÔNG BÁO CH? X? LÝ
            text = f"""? **ÐANG X? LÝ GIAO D?CH**

?? **S? ti?n:** {transaction.amount:,}d
?? **Mã GD:** `{transaction_code}`

? **Ðã ghi nh?n yêu c?u n?p ti?n c?a b?n.**

?? **H? th?ng dang ch? xác nh?n t? ngân hàng.**
?? **Ti?n s? du?c c?ng t? d?ng sau 1-5 phút.**

?? **KHÔNG C?N B?M NÚT NHI?U L?N**
?? **B?n s? nh?n thông báo khi giao d?ch hoàn t?t.**"""
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"L?i deposit_check_callback: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="? **L?I X? LÝ**\n\nVui lòng th? l?i sau.",
            parse_mode='Markdown'
        )

async def check_deposit_status(update: Update, context: Context):
    """L?nh ki?m tra tr?ng thái giao d?ch th? công"""
    try:
        if not context.args:
            await update.message.reply_text(
                "? **CÚ PHÁP SAI**\n\nVui lòng nh?p: `/check MÃ_GD`\nVí d?: `/check MANUAL_20260307153425`",
                parse_mode='Markdown'
            )
            return
        
        code = context.args[0].upper()
        
        # Ki?m tra trên Render
        try:
            response = requests.post(
                f"{RENDER_URL}/api/check-transaction",
                json={'code': code},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('exists'):
                    status_text = {
                        'pending': '? Ðang ch? x? lý',
                        'success': '? Ðã thành công',
                        'failed': '? Th?t b?i'
                    }.get(data['status'], '? Không xác d?nh')
                    
                    # Ki?m tra thêm trên local d? xác nh?n
                    from main import app
from bot import app
                    with app.app_context():
                        local_trans = Transaction.query.filter_by(transaction_code=code).first()
                        if local_trans:
                            user = User.query.get(local_trans.user_id)
                            local_status = local_trans.status
                            local_balance = user.balance if user else 0
                        else:
                            local_status = 'not_found'
                            local_balance = 0
                    
                    await update.message.reply_text(
                        f"?? **KI?M TRA GIAO D?CH {code}**\n\n"
                        f"?? **Render:** {status_text}\n"
                        f"?? **Local:** {local_status}\n"
                        f"?? **S? ti?n:** {data['amount']:,}d\n"
                        f"?? **User ID:** {data['user_id']}\n"
                        f"?? **S? du hi?n t?i:** {local_balance:,}d\n\n"
                        f"{'? Giao d?ch dã thành công!' if data['status'] == 'success' else '? Vui lòng ch? x? lý...'}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"? **KHÔNG TÌM TH?Y**\n\nMã giao d?ch `{code}` không t?n t?i trong h? th?ng.",
                        parse_mode='Markdown'
                    )
            else:
                await update.message.reply_text(
                    f"? **L?I K?T N?I**\n\nKhông th? ki?m tra tr?ng thái. Vui lòng th? l?i sau.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"L?i check status: {e}")
            await update.message.reply_text(
                f"? **L?I**\n\nKhông th? k?t n?i d?n server.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"L?i check_deposit_status: {e}")
        await update.message.reply_text(
            "? **L?I X? LÝ**\n\nVui lòng th? l?i sau.",
            parse_mode='Markdown'
        )

# Hàm ti?n ích d? fix user n?u c?n
def fix_user_manual(user_id, username, amount, transaction_code):
    """Fix user th? công (dùng khi c?n)"""
    try:
        # Push lên Render
        response = requests.post(
            f"{RENDER_URL}/api/check-user",
            json={'user_id': user_id, 'username': username},
            timeout=5
        )
        print(f"Push user: {response.json()}")
        
        # Push transaction
        response = requests.post(
            f"{RENDER_URL}/api/sync-pending",
            json={'transactions': [{
                'code': transaction_code,
                'amount': amount,
                'user_id': user_id,
                'username': username
            }]},
            timeout=5
        )
        print(f"Push transaction: {response.json()}")
        
        # C?p nh?t local
        from main import app
from bot import app
        with app.app_context():
            user = User.query.filter_by(user_id=user_id).first()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    balance=0,
                    created_at=datetime.now()
                )
                db.session.add(user)
                db.session.flush()
            
            user.balance += amount
            
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                type='deposit',
                status='success',
                transaction_code=transaction_code,
                description=f"Manual fix",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()
            
            print(f"? Ðã fix user {user_id} - {username} +{amount}d")
            return True
    except Exception as e:
        print(f"? L?i fix: {e}")
        return False
