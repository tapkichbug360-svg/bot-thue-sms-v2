from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from bot import app
from database.models import User, db
from bot import app
from datetime import datetime
import logging
import os
import requests
from bot import app

logger = logging.getLogger(__name__)

MB_ACCOUNT = os.getenv('MB_ACCOUNT', '666666291005')
MB_NAME = os.getenv('MB_NAME', 'NGUYEN THE LAM')
RENDER_URL = os.getenv('RENDER_URL', 'https://bot-thue-sms-v2.onrender.com')

async def sync_balance_with_render(user_id):
    """Ð?ng b? s? du t? Render v? local"""
    try:
        response = requests.post(
            f"{RENDER_URL}/api/force-sync-user",
            json={'user_id': user_id},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            render_balance = data['balance']
            
            from main import app
from bot import app
            with app.app_context():
                user = User.query.filter_by(user_id=user_id).first()
                if user and user.balance != render_balance:
                    old_balance = user.balance
                    user.balance = render_balance
                    
                    # C?p nh?t các giao d?ch
                    for trans in data['transactions']:
                        # Tìm và c?p nh?t transaction
                        from database.models import Transaction
from bot import app
                        transaction = Transaction.query.filter_by(
                            transaction_code=trans['code']
                        ).first()
                        if transaction:
                            transaction.status = trans['status']
                            transaction.updated_at = datetime.now()
                    
                    db.session.commit()
                    logger.info(f"? Ð?ng b? user {user_id}: {old_balance}d ? {render_balance}d")
                    return True
            return True
        return False
    except Exception as e:
        logger.error(f"? L?i d?ng b? user {user_id}: {e}")
        return False

async def start_command(update: Update, context: Context):
    """X? lý l?nh /start"""
    user = update.effective_user
    
    from main import app
from bot import app
    with app.app_context():
        existing_user = User.query.filter_by(user_id=user.id).first()
        if not existing_user:
            new_user = User(
                user_id=user.id,
                username=user.username or user.first_name,
                balance=0,
                created_at=datetime.now(),
                last_active=datetime.now()
            )
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"? Ngu?i dùng m?i: {user.id} - {user.first_name}")
            
            # Push user m?i lên Render
            try:
                push_response = requests.post(
                    f"{RENDER_URL}/api/check-user",
                    json={'user_id': user.id, 'username': user.username or user.first_name},
                    timeout=5
                )
                logger.info(f"? Ðã push user m?i lên Render: {push_response.status_code}")
            except:
                pass
        else:
            existing_user.last_active = datetime.now()
            db.session.commit()
            logger.info(f"?? Ngu?i dùng cu: {user.id} - {user.first_name}")
            
            # Ð?ng b? s? du t? Render
            await sync_balance_with_render(user.id)
    
    # T?o keyboard menu chính
    keyboard = [
        [InlineKeyboardButton("?? Thuê s?", callback_data='menu_rent'),
         InlineKeyboardButton("?? S? dang thuê", callback_data='menu_rent_list')],
        [InlineKeyboardButton("?? S? du", callback_data='menu_balance'),
         InlineKeyboardButton("?? N?p ti?n", callback_data='menu_deposit')],
        [InlineKeyboardButton("?? L?ch s?", callback_data='menu_history'),
         InlineKeyboardButton("?? Tài kho?n", callback_data='menu_profile')],
        [InlineKeyboardButton("? Hu?ng d?n", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = (
        f"?? **Chào m?ng {user.first_name} d?n v?i Bot Thuê SMS!**\n\n"
        f"?? Bot cung c?p d?ch v? thuê s? di?n tho?i ?o:\n"
        f"• Facebook • Google • Tiktok • Shopee • Các d?ch v? khác\n\n"
        f"?? **TUÂN TH? PHÁP LU?T:**\n"
        f"• Nghiêm c?m l?a d?o, cá d?, bank ?o\n"
        f"• Vi ph?m s? khóa tài kho?n\n\n"
        f"?? **MBBANK**\n"
        f"?? **S? TK:** `{MB_ACCOUNT}`\n"
        f"?? **Ch? TK:** `{MB_NAME}`\n\n"
        f"?? **Hu?ng d?n nhanh:**\n"
        f"• Ch?n 'Thuê s?' d? b?t d?u\n"
        f"• Ch?n 'S? dang thuê' d? xem các s? dã thuê"
    )
    
    await update.message.reply_text(
        welcome_msg, 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

async def menu_command(update: Update, context: Context):
    """Hi?n th? menu chính"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Ð?ng b? s? du tru?c khi hi?n th? menu
    user = update.effective_user
    await sync_balance_with_render(user.id)
    
    keyboard = [
        [InlineKeyboardButton("?? Thuê s?", callback_data='menu_rent'),
         InlineKeyboardButton("?? S? dang thuê", callback_data='menu_rent_list')],
        [InlineKeyboardButton("?? S? du", callback_data='menu_balance'),
         InlineKeyboardButton("?? N?p ti?n", callback_data='menu_deposit')],
        [InlineKeyboardButton("?? L?ch s?", callback_data='menu_history'),
         InlineKeyboardButton("?? Tài kho?n", callback_data='menu_profile')],
        [InlineKeyboardButton("? Hu?ng d?n", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "?? **MENU CHÍNH**\n\nCh?n ch?c nang b?n mu?n s? d?ng:"
    
    if query:
        try:
            await query.edit_message_text(
                text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"L?i edit message: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

async def cancel(update: Update, context: Context):
    """H?y thao tác hi?n t?i"""
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("?? QUAY L?I MENU", callback_data="menu_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "? **ÐÃ H?Y THAO TÁC!**\n\nB?n có th? ch?n ch?c nang khác."
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: Context):
    """Hi?n th? hu?ng d?n chi ti?t"""
    text = (
        "? **HU?NG D?N CHI TI?T**\n\n"
        "1?? **N?p ti?n:**\n"
        "   • Ch?n 'N?p ti?n' ? Ch?n s? ti?n\n"
        "   • Chuy?n kho?n d?n tài kho?n:\n"
        f"     ?? {MB_ACCOUNT} - {MB_NAME}\n"
        "   • Nh?p n?i dung chính xác d? du?c c?ng t? d?ng\n\n"
        "2?? **Thuê s?:**\n"
        "   • Ch?n 'Thuê s?' ? Ch?n d?ch v?\n"
        "   • Ch?n nhà m?ng ? Xác nh?n\n"
        "   • Bot t? d?ng ki?m tra OTP trong 5 phút\n\n"
        "3?? **Qu?n lý s?:**\n"
        "   • 'S? dang thuê': Xem t?t c? s? dang active\n"
        "   • Click vào s? d? xem chi ti?t/h?y s?\n"
        "   • H?y s? du?c hoàn ti?n (n?u chua có OTP)\n\n"
        "4?? **Ki?m tra giao d?ch:**\n"
        "   • Dùng l?nh `/check MÃ_GD` d? xem tr?ng thái\n"
        "   • Ví d?: `/check MANUAL_20260307153425`\n\n"
        "?? **QUY Ð?NH:**\n"
        "• Không l?a d?o, cá d?, dánh b?c\n"
        "• Không t?o bank ?o, ti?n ?o\n"
        "• Vi ph?m s? khóa tài kho?n vinh vi?n\n\n"
        f"?? **H? tr?:** Liên h? admin @makkllai"
    )
    
    keyboard = [[InlineKeyboardButton("?? Quay l?i menu", callback_data="menu_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

async def check_command(update: Update, context: Context):
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
                        from database.models import Transaction, User
from bot import app
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
        except requests.exceptions.ConnectionError:
            await update.message.reply_text(
                "? **L?I K?T N?I**\n\nKhông th? k?t n?i d?n server Render. Vui lòng th? l?i sau.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"L?i check status: {e}")
            await update.message.reply_text(
                f"? **L?I**\n\nKhông th? ki?m tra tr?ng thái. Vui lòng th? l?i sau.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"L?i check_deposit_status: {e}")
        await update.message.reply_text(
            "? **L?I X? LÝ**\n\nVui lòng th? l?i sau.",
            parse_mode='Markdown'
        )

async def balance_command(update: Update, context: Context):
    """Xem s? du tài kho?n - CÓ Ð?NG B? V?I RENDER"""
    user = update.effective_user
    
    # Ð?ng b? s? du t? Render tru?c
    await sync_balance_with_render(user.id)
    
    from main import app
from bot import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        
        if not db_user:
            text = "? KHÔNG TÌM TH?Y TÀI KHO?N\n\nVui lòng g?i /start d? dang ký."
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        balance = db_user.balance
        total_spent = db_user.total_spent
        total_rentals = db_user.total_rentals
        
        text = (
            f"?? **S? DU TÀI KHO?N**\n\n"
            f"• **User ID:** `{user.id}`\n"
            f"• **Tên:** {user.first_name}\n"
            f"• **Username:** @{user.username or 'N/A'}\n\n"
            f"?? **S? du hi?n t?i:** `{balance:,}d`\n"
            f"?? **Ðã thuê:** {total_rentals} s?\n"
            f"?? **T?ng chi:** {total_spent:,}d\n\n"
            f"?? **Ch?n thao tác:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("?? N?p ti?n", callback_data="menu_deposit")],
            [InlineKeyboardButton("?? Thuê s?", callback_data="menu_rent")],
            [InlineKeyboardButton("?? Menu chính", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
