from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from bot import app
from database.models import User, Rental, db
from bot import app
from datetime import datetime, timedelta
import requests
import os
import logging
import time
import asyncio
from bot import app


logger = logging.getLogger(__name__)

API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL')

# Cache d? tránh g?i API quá nhi?u
services_cache = []
services_cache_time = 0
networks_cache = []
networks_cache_time = 0

async def delete_previous_menu(update: Update, context: Context):
    """Xóa menu tru?c dó d? tránh nhi?u menu ch?ng lên nhau"""
    try:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.delete()
    except Exception as e:
        logger.error(f"L?i xóa menu cu: {e}")

async def get_services():
    """L?y danh sách d?ch v? t? API"""
    global services_cache, services_cache_time
    
    if services_cache and time.time() - services_cache_time < 300:
        return services_cache
    
    try:
        url = f"{BASE_URL}/service/get_service_by_api_key?api_key={API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 200:
            services_cache = data.get('data', [])
            services_cache_time = time.time()
            return services_cache
        else:
            logger.error(f"L?i API services: {data}")
            return []
    except Exception as e:
        logger.error(f"L?i k?t n?i API services: {e}")
        return []

async def get_networks():
    """L?y danh sách nhà m?ng t? API"""
    global networks_cache, networks_cache_time
    
    if networks_cache and time.time() - networks_cache_time < 300:
        return networks_cache
    
    try:
        url = f"{BASE_URL}/network/get-network-by-api-key?api_key={API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 200:
            networks_cache = data.get('data', [])
            networks_cache_time = time.time()
            return networks_cache
        else:
            logger.error(f"L?i API networks: {data}")
            return []
    except Exception as e:
        logger.error(f"L?i k?t n?i API networks: {e}")
        return []

async def get_account_info():
    """L?y thông tin tài kho?n API"""
    try:
        url = f"{BASE_URL}/yourself/information-by-api-key?api_key={API_KEY}"
        response = requests.get(url)
        data = response.json()
        if data.get('status') == 200:
            return data.get('data', {})
        return None
    except Exception as e:
        logger.error(f"L?i l?y thông tin tài kho?n: {e}")
        return None

async def rent_command(update: Update, context: Context):
    """Hi?n th? danh sách d?ch v? (dã ?n s? du API)"""
    logger.info("?? rent_command du?c g?i")
    
    # Xóa menu cu tru?c khi hi?n th? menu m?i
    await delete_previous_menu(update, context)
    
    # Ki?m tra user có b? ban không
    user = update.effective_user
    from main import app
from bot import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        if db_user and db_user.is_banned:
            text = "? **TÀI KHO?N C?A B?N ÐÃ B? KHÓA**\n\nVui lòng liên h? admin d? bi?t thêm chi ti?t."
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode='Markdown'
            )
            return
    
    # Hi?n th? tr?ng thái dang t?i
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="?? **ÐANG T?I DANH SÁCH D?CH V?...**\n\nVui lòng ch? trong giây lát.",
        parse_mode='Markdown'
    )
    
    services = await get_services()
    
    if not services:
        await loading_msg.edit_text(
            "? **KHÔNG TH? L?Y DANH SÁCH D?CH V?**\n\n"
            "• Ki?m tra k?t n?i API\n"
            "• Th? l?i sau vài phút\n"
            "• Liên h? admin n?u l?i ti?p di?n",
            parse_mode='Markdown'
        )
        return
    
    # L?c các d?ch v? b? c?m
    banned_services = ['ZALO', 'TELEGRAM', 'BANK', 'TIENAO', 'CRYPTO']
    filtered_services = []
    for sv in services:
        name_upper = sv['name'].upper()
        is_banned = False
        for banned in banned_services:
            if banned in name_upper:
                is_banned = True
                break
        if not is_banned:
            filtered_services.append(sv)
    
    if not filtered_services:
        await loading_msg.edit_text(
            "? **KHÔNG CÓ D?CH V? NÀO KH? D?NG**\n\n"
            "T?t c? d?ch v? hi?n dang t?m ngung.",
            parse_mode='Markdown'
        )
        return
    
    # T?o keyboard v?i giá dã c?ng 1000d - HI?N TH? T?T C? D?CH V?
    keyboard = []
    row = []
    for i, sv in enumerate(filtered_services):  # B? gi?i h?n 20
        try:
            original_price = int(float(sv['price']))
            final_price = original_price + 1000
        except:
            original_price = 1200
            final_price = 2200
            
        button = InlineKeyboardButton(
            f"{sv['name']} - {final_price:,}d",
            callback_data=f"rent_service_{sv['id']}_{sv['name']}_{original_price}"
        )
        row.append(button)
        
        # 2 nút trên 1 hàng
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Thêm hàng cu?i cùng n?u còn
    if row:
        keyboard.append(row)
    
    # Thêm nút di?u hu?ng
    keyboard.append([InlineKeyboardButton("?? DANH SÁCH S? C?A TÔI", callback_data="menu_rent_list")])
    keyboard.append([InlineKeyboardButton("?? QUAY L?I MENU", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Ð?m s? d?ch v?
    total_services = len(filtered_services)
    
    text = (
        f"?? **THUÊ S? NH?N OTP**\n\n"
        f"?? **T?ng s? d?ch v?:** {total_services}\n\n"
        f"?? **TUÂN TH? PHÁP LU?T:**\n"
        f"• Nghiêm c?m dánh b?c, cá d?, l?a d?o\n"
        f"• Nghiêm c?m t?o bank ?o, ti?n ?o\n"
        f"• D?ch v? ZALO, Telegram hi?n dang C?M!\n"
        f"• M?i vi ph?m s? khóa tài kho?n vinh vi?n\n\n"
        f"?? **Ch?n d?ch v? bên du?i:**"
    )
    
    await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_service_callback(update: Update, context: Context):
    """X? lý khi ch?n d?ch v?"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        service_id = data[2]
        service_name = data[3]
        original_price = int(float(data[4]))
        final_price = original_price + 1000
    except Exception as e:
        logger.error(f"L?i parse data: {e}")
        await query.edit_message_text("? **L?I D? LI?U**\n\nVui lòng ch?n l?i d?ch v?.")
        return
    
    # Luu thông tin d?ch v? dã ch?n
    context.user_data['rent'] = {
        'service_id': service_id,
        'service_name': service_name,
        'final_price': final_price,
        'original_price': original_price
    }
    
    # Xóa menu hi?n t?i
    try:
        await query.message.delete()
    except:
        pass
    
    # Hi?n th? tr?ng thái dang t?i
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="?? **ÐANG T?I DANH SÁCH NHÀ M?NG...**",
        parse_mode='Markdown'
    )
    
    networks = await get_networks()
    
    if not networks:
        keyboard = [[InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.edit_text(
            "? **KHÔNG TH? L?Y DANH SÁCH NHÀ M?NG**\n\nVui lòng th? l?i sau.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # L?c nhà m?ng dang ho?t d?ng
    active_networks = [net for net in networks if net.get('status') == 1]
    
    if not active_networks:
        keyboard = [[InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.edit_text(
            "? **KHÔNG CÓ NHÀ M?NG NÀO HO?T Ð?NG**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for net in active_networks[:10]:
        keyboard.append([InlineKeyboardButton(
            f"?? {net['name']}",
            callback_data=f"rent_network_{net['id']}_{net['name']}"
        )])
    
    keyboard.append([InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"?? **{service_name}**\n"
        f"?? **Ch?n nhà m?ng:**"
    )
    
    await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_network_callback(update: Update, context: Context):
    """X? lý khi ch?n nhà m?ng"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        network_id = data[2]
        network_name = data[3]
    except Exception as e:
        logger.error(f"L?i parse network: {e}")
        await query.edit_message_text("? **L?I D? LI?U**\n\nVui lòng ch?n l?i.")
        return
    
    rent_info = context.user_data.get('rent', {})
    service_id = rent_info.get('service_id')
    service_name = rent_info.get('service_name')
    final_price = rent_info.get('final_price')
    original_price = rent_info.get('original_price')
    
    if not service_id or not final_price:
        await query.edit_message_text("? **L?I!**\n\nVui lòng ch?n l?i d?ch v?.")
        return
    
    user = update.effective_user
    from main import app
from bot import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        current_balance = db_user.balance if db_user else 0
    
    # Xóa menu hi?n t?i
    await query.message.delete()
    
    keyboard = [
        [InlineKeyboardButton("? XÁC NH?N THUÊ", callback_data=f"rent_confirm_{service_id}_{final_price}_{network_id}")],
        [InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"?? **XÁC NH?N THUÊ S?**\n\n"
        f"• **D?ch v?:** {service_name}\n"
        f"• **Nhà m?ng:** {network_name}\n"
        f"• **S? du c?a b?n:** {current_balance:,}d\n\n"
        f"?? **Luu ý:**\n"
        f"• S? ti?n s? du?c tr? ngay sau khi xác nh?n\n"
        f"• Có th? h?y và du?c hoàn ti?n n?u chua nh?n OTP\n"
        f"• S? có hi?u l?c trong 5 phút\n\n"
        f"? **Xác nh?n thuê s??**"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def rent_confirm_callback(update: Update, context: Context):
    """Xác nh?n thuê s? - G?i API l?y s?"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        service_id = data[2]
        final_price = int(data[3])
        network_id = data[4]
    except Exception as e:
        logger.error(f"L?i parse confirm: {e}")
        await query.edit_message_text("? **L?I D? LI?U**\n\nVui lòng ch?n l?i.")
        return
    
    user = update.effective_user
    
    from main import app
from bot import app
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        
        if not db_user:
            await query.edit_message_text("? **KHÔNG TÌM TH?Y TÀI KHO?N**\n\nVui lòng g?i /start d? dang ký.")
            return
        
        if db_user.balance < final_price:
            shortage = final_price - db_user.balance
            keyboard = [
                [InlineKeyboardButton("?? N?P TI?N NGAY", callback_data="menu_deposit")],
                [InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"? **S? DU KHÔNG Ð?!**\n\n"
                f"• **C?n:** {final_price:,}d\n"
                f"• **Có:** {db_user.balance:,}d\n"
                f"• **Thi?u:** {shortage:,}d\n\n"
                f"Vui lòng n?p thêm ti?n d? ti?p t?c.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Xóa menu hi?n t?i
        await query.message.delete()
        
        loading_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="?? **ÐANG X? LÝ YÊU C?U...**\n\n?? Vui lòng ch? trong giây lát.",
            parse_mode='Markdown'
        )
        
        try:
            url = f"{BASE_URL}/sim/get_sim"
            
            # T?o params
            params = {
                'api_key': API_KEY,
                'service_id': service_id
            }
            
            # Thêm network_id n?u có
            if network_id and network_id != 'None':
                params['network_id'] = network_id
            
            logger.info(f"?? G?i API l?y s?: service_id={service_id}, network_id={network_id}")
            response = requests.get(url, params=params, timeout=15)
            response_data = response.json()
            
            logger.info(f"API response: {response_data}")
            
            if response_data.get('status') == 200:
                sim_data = response_data.get('data', {})
                phone = sim_data.get('phone')
                otp_id = sim_data.get('otpId')
                sim_id = sim_data.get('simId')
                actual_price = sim_data.get('payment', final_price - 1000)
                
                old_balance = db_user.balance
                db_user.balance -= final_price
                db_user.total_spent += final_price
                db_user.total_rentals += 1
                
                rent_info = context.user_data.get('rent', {})
                
                rental = Rental(
                    user_id=user.id,
                    service_id=int(service_id),
                    service_name=rent_info['service_name'],
                    phone_number=phone,
                    otp_id=otp_id,
                    sim_id=sim_id,
                    cost=actual_price,
                    price_charged=final_price,
                    status='waiting',
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(minutes=5)
                )
                db.session.add(rental)
                db.session.commit()
                
                logger.info(f"? User {user.id} thuê s? {phone} thành công")
                logger.info(f"?? Ðã tr? {final_price}d (t? {old_balance}d còn {db_user.balance}d)")
                
                # Luu rental vào context
                if 'active_rentals' not in context.user_data:
                    context.user_data['active_rentals'] = []
                context.user_data['active_rentals'].append({
                    'id': rental.id,
                    'phone': phone,
                    'service': rent_info['service_name'],
                    'expires_at': rental.expires_at.isoformat()
                })
                
                keyboard = [
                    [InlineKeyboardButton(f"?? {phone} - {rent_info['service_name']}", callback_data=f"rent_view_{rental.id}")],
                    [InlineKeyboardButton("?? DANH SÁCH S?", callback_data="menu_rent_list")],
                    [InlineKeyboardButton("? THUÊ S? KHÁC", callback_data="menu_rent")],
                    [InlineKeyboardButton("?? MENU CHÍNH", callback_data="menu_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                text = (
                    f"? **THUÊ S? THÀNH CÔNG!**\n\n"
                    f"?? **S?:** `{phone}`\n"
                    f"?? **D?ch v?:** {rent_info['service_name']}\n"
                    f"?? **Ðã thanh toán:** {final_price:,}d\n"
                    f"?? **S? du còn l?i:** {db_user.balance:,}d\n"
                    f"? **H?t h?n lúc:** {rental.expires_at.strftime('%H:%M:%S')}\n\n"
                    f"?? **T? Ð?NG KI?M TRA OTP**\n"
                    f"• Bot s? t? d?ng ki?m tra và báo khi có OTP\n"
                    f"• B?n có th? theo dõi s? qua menu trên"
                )
                
                await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
                # B?t d?u t? d?ng ki?m tra OTP
                asyncio.create_task(
                    auto_check_otp_task(
                        context.bot,
                        chat_id=update.effective_chat.id,
                        otp_id=otp_id,
                        rental_id=rental.id,
                        user_id=user.id,
                        service_name=rent_info['service_name'],
                        phone=phone
                    )
                )
                
            else:
                error_msg = response_data.get('message', 'Không rõ l?i')
                await loading_msg.edit_text(
                    f"? **L?I T? MÁY CH?**\n\n"
                    f"?? Thông báo: {error_msg}\n\n"
                    f"Vui lòng th? l?i sau ho?c ch?n d?ch v? khác.",
                    parse_mode='Markdown'
                )
                
        except requests.exceptions.Timeout:
            await loading_msg.edit_text(
                "? **TIMEOUT - MÁY CH? KHÔNG PH?N H?I**\n\n"
                "Vui lòng th? l?i sau.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"L?i thuê s?: {e}")
            import traceback
from bot import app
            traceback.print_exc()
            await loading_msg.edit_text(
                "? **L?I K?T N?I**\n\n"
                "Vui lòng th? l?i sau.",
                parse_mode='Markdown'
            )

async def rent_check_callback(update: Update, context: Context):
    """Ki?m tra OTP th? công - G?I FILE AUDIO N?U CÓ"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        otp_id = data[2]
        rental_id = int(data[3])
    except Exception as e:
        logger.error(f"L?i parse check: {e}")
        await query.edit_message_text("? **L?I D? LI?U**\n\nVui lòng th? l?i.")
        return
    
    # Hi?n th? tr?ng thái dang ki?m tra
    await query.edit_message_text(
        "?? **ÐANG KI?M TRA OTP...**\n\nVui lòng ch? trong giây lát.",
        parse_mode='Markdown'
    )
    
    try:
        # G?i API ki?m tra OTP
        url = f"{BASE_URL}/otp/get_otp_by_phone_api_key"
        params = {
            'api_key': API_KEY,
            'otp_id': otp_id
        }
        
        logger.info(f"?? Ki?m tra OTP cho otp_id={otp_id}")
        response = requests.get(url, params=params, timeout=10)
        response_data = response.json()
        
        logger.info(f"API check OTP response: {response_data}")
        
        from main import app
from bot import app
        with app.app_context():
            rental = Rental.query.get(rental_id)
            
            if not rental:
                await query.edit_message_text(
                    "? **KHÔNG TÌM TH?Y THÔNG TIN THUÊ S?**\n\n"
                    "Vui lòng th? l?i ho?c liên h? admin.",
                    parse_mode='Markdown'
                )
                return
            
            status = response_data.get('status')
            
            if status == 200:
                otp_data = response_data.get('data', {})
                otp_code = otp_data.get('code')
                content = otp_data.get('content', '')
                sender = otp_data.get('senderName', '')
                audio_url = otp_data.get('audio')  # URL file audio cu?c g?i
                
                # C?p nh?t tr?ng thái rental
                rental.status = 'success'
                rental.otp_code = otp_code or "Audio OTP"
                rental.content = content
                rental.updated_at = datetime.now()
                db.session.commit()
                
                # === X? LÝ AUDIO ===
                if audio_url:
                    try:
                        logger.info(f"?? Ðang t?i audio t?: {audio_url}")
                        
                        # T?i file audio
                        audio_response = requests.get(audio_url, timeout=15)
                        
                        if audio_response.status_code == 200:
                            # Xác d?nh d?nh d?ng file
                            content_type = audio_response.headers.get('content-type', 'audio/mpeg')
                            file_ext = 'mp3'
                            if 'wav' in content_type:
                                file_ext = 'wav'
                            elif 'ogg' in content_type:
                                file_ext = 'ogg'
                            
                            # G?i file audio tr?c ti?p
                            await context.bot.send_audio(
                                chat_id=update.effective_chat.id,
                                audio=audio_response.content,
                                filename=f"otp_call_{rental_id}.{file_ext}",
                                title=f"?? Cu?c g?i OTP t? {rental.service_name}",
                                caption=(
                                    f"?? **CU?C G?I OTP**\n\n"
                                    f"• **D?ch v?:** {rental.service_name}\n"
                                    f"• **S? di?n tho?i:** `{rental.phone_number}`\n"
                                    f"• **Th?i gian:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
                                    f"?? **B?m play d? nghe l?i cu?c g?i**"
                                ),
                                parse_mode='Markdown'
                            )
                            logger.info(f"? Ðã g?i file audio cu?c g?i cho rental {rental_id}")
                            
                        else:
                            logger.error(f"? Không th? t?i audio, status code: {audio_response.status_code}")
                            # G?i link n?u không t?i du?c
                            keyboard = [[InlineKeyboardButton("?? NGHE OTP TRÊN WEB", url=audio_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=(
                                    f"?? **CÓ OTP D?NG CU?C G?I**\n\n"
                                    f"• **D?ch v?:** {rental.service_name}\n"
                                    f"• **S?:** `{rental.phone_number}`\n\n"
                                    f"? Không th? t?i file audio t? d?ng.\n"
                                    f"?? B?m nút bên du?i d? nghe trên web:"
                                ),
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            )
                            
                    except Exception as e:
                        logger.error(f"? L?i x? lý audio: {e}")
                        # G?i link d? phòng
                        keyboard = [[InlineKeyboardButton("?? NGHE OTP", url=audio_url)]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=(
                                f"?? **CÓ OTP D?NG CU?C G?I**\n\n"
                                f"• **D?ch v?:** {rental.service_name}\n"
                                f"• **S?:** `{rental.phone_number}`\n\n"
                                f"?? B?m nút d? nghe trên web:"
                            ),
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                
                # === G?I OTP D?NG TEXT N?U CÓ ===
                if otp_code:
                    text_message = (
                        f"? **NH?N OTP THÀNH CÔNG!**\n\n"
                        f"?? **Mã OTP:** `{otp_code}`\n"
                        f"?? **N?i dung:** {content}\n"
                        f"?? **Ngu?i g?i:** {sender}\n"
                        f"?? **D?ch v?:** {rental.service_name}\n"
                        f"?? **S?:** `{rental.phone_number}`"
                    )
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=text_message,
                        parse_mode='Markdown'
                    )
                elif not audio_url:
                    # Không có c? audio và text
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"? **ÐÃ NH?N OTP**\n\n?? **D?ch v?:** {rental.service_name}\n?? **S?:** `{rental.phone_number}`",
                        parse_mode='Markdown'
                    )
                
                # Xóa menu cu
                await query.delete_message()
                
            elif status == 202:
                # Chua có OTP
                expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
                await query.edit_message_text(
                    f"? **CHUA CÓ OTP**\n\n"
                    f"• **S?:** `{rental.phone_number}`\n"
                    f"• **D?ch v?:** {rental.service_name}\n"
                    f"• **Còn:** {expires_in} phút\n\n"
                    f"Vui lòng th? l?i sau vài giây.",
                    parse_mode='Markdown'
                )
                
            elif status == 312:
                await query.edit_message_text(
                    f"? **ÐANG CH? OTP**\n\n"
                    f"• **S?:** `{rental.phone_number}`\n"
                    f"• **D?ch v?:** {rental.service_name}",
                    parse_mode='Markdown'
                )
                
            elif status == 400:
                rental.status = 'expired'
                rental.updated_at = datetime.now()
                db.session.commit()
                
                await query.edit_message_text(
                    f"? **OTP ÐÃ H?T H?N**\n\n"
                    f"S? `{rental.phone_number}` dã h?t h?n.\n"
                    f"Vui lòng thuê s? m?i.",
                    parse_mode='Markdown'
                )
                
            else:
                error_msg = response_data.get('message', 'Không xác d?nh')
                await query.edit_message_text(
                    f"? **L?I KI?M TRA OTP**\n\n"
                    f"L?i: {error_msg}\n\n"
                    f"Vui lòng th? l?i sau.",
                    parse_mode='Markdown'
                )
                
    except requests.exceptions.Timeout:
        await query.edit_message_text(
            "? **TIMEOUT - MÁY CH? KHÔNG PH?N H?I**\n\n"
            "Vui lòng th? l?i sau.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"L?i ki?m tra OTP: {e}")
        import traceback
from bot import app
        traceback.print_exc()
        await query.edit_message_text(
            "? **L?I K?T N?I**\n\n"
            "Vui lòng th? l?i sau.",
            parse_mode='Markdown'
        )

async def auto_check_otp_task(bot, chat_id: int, otp_id: str, rental_id: int, user_id: int, service_name: str, phone: str):
    """T? d?ng ki?m tra OTP - G?I FILE AUDIO KHI CÓ CU?C G?I"""
    logger.info(f"?? B?t d?u auto-check OTP cho rental {rental_id}")
    
    max_checks = 60
    check_count = 0
    
    while check_count < max_checks:
        check_count += 1
        logger.info(f"?? Auto-check OTP l?n {check_count}/{max_checks} cho rental {rental_id}")
        
        try:
            url = f"{BASE_URL}/otp/get_otp_by_phone_api_key"
            params = {'api_key': API_KEY, 'otp_id': otp_id}
            response = requests.get(url, params=params, timeout=5)
            response_data = response.json()
            
            status = response_data.get('status')
            
            if status == 200:
                otp_data = response_data.get('data', {})
                otp_code = otp_data.get('code')
                content = otp_data.get('content', '')
                sender = otp_data.get('senderName', '')
                audio_url = otp_data.get('audio')  # URL file audio cu?c g?i
                
                from main import app
from bot import app
                with app.app_context():
                    rental = Rental.query.get(rental_id)
                    if rental and rental.status == 'waiting':
                        rental.status = 'success'
                        rental.otp_code = otp_code or "G?i di?n"
                        rental.content = content
                        rental.updated_at = datetime.now()
                        db.session.commit()
                        
                        logger.info(f"? Auto-check: Nh?n OTP cho rental {rental_id}")
                        
                        # === G?I FILE AUDIO CU?C G?I ===
                        if audio_url:
                            try:
                                logger.info(f"?? Ðang t?i audio cu?c g?i t?: {audio_url}")
                                
                                # T?i file audio
                                audio_response = requests.get(audio_url, timeout=15)
                                
                                if audio_response.status_code == 200:
                                    # Xác d?nh d?nh d?ng file
                                    content_type = audio_response.headers.get('content-type', 'audio/mpeg')
                                    file_ext = 'mp3'  # M?c d?nh
                                    if 'wav' in content_type:
                                        file_ext = 'wav'
                                    elif 'ogg' in content_type:
                                        file_ext = 'ogg'
                                    
                                    # G?i file audio lên Telegram
                                    await bot.send_audio(
                                        chat_id=chat_id,
                                        audio=audio_response.content,
                                        filename=f"otp_call_{rental_id}.{file_ext}",
                                        title=f"?? Cu?c g?i OTP t? {service_name}",
                                        caption=(
                                            f"?? **CU?C G?I OTP**\n\n"
                                            f"• **D?ch v?:** {service_name}\n"
                                            f"• **S? di?n tho?i:** `{phone}`\n"
                                            f"• **Th?i gian:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
                                            f"?? **B?m play d? nghe l?i cu?c g?i**"
                                        ),
                                        parse_mode='Markdown'
                                    )
                                    logger.info(f"? Ðã g?i file audio cu?c g?i cho rental {rental_id}")
                                    
                                    # G?i thêm OTP text n?u có
                                    if otp_code:
                                        await bot.send_message(
                                            chat_id=chat_id,
                                            text=f"? **MÃ OTP:** `{otp_code}`\n?? {content}",
                                            parse_mode='Markdown'
                                        )
                                        
                                else:
                                    logger.error(f"? Không th? t?i audio, status code: {audio_response.status_code}")
                                    # Fallback: g?i link n?u không t?i du?c
                                    keyboard = [[InlineKeyboardButton("?? NGHE OTP TRÊN WEB", url=audio_url)]]
                                    reply_markup = InlineKeyboardMarkup(keyboard)
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=(
                                            f"?? **CÓ OTP D?NG CU?C G?I**\n\n"
                                            f"• **D?ch v?:** {service_name}\n"
                                            f"• **S?:** `{phone}`\n\n"
                                            f"? Không th? t?i file audio t? d?ng.\n"
                                            f"?? B?m nút bên du?i d? nghe trên web:"
                                        ),
                                        reply_markup=reply_markup,
                                        parse_mode='Markdown'
                                    )
                                    
                            except Exception as e:
                                logger.error(f"? L?i x? lý audio: {e}")
                                # Fallback
                                keyboard = [[InlineKeyboardButton("?? NGHE OTP", url=audio_url)]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=f"?? **CÓ OTP D?NG CU?C G?I**\n\n?? B?m nút d? nghe:",
                                    reply_markup=reply_markup,
                                    parse_mode='Markdown'
                                )
                        
                        # N?u không có audio, ch? g?i text
                        elif otp_code:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=f"? **MÃ OTP:** `{otp_code}`\n?? {content}",
                                parse_mode='Markdown'
                            )
                        
                        return
                        
            elif status in [202, 312]:
                # Ðang ch? OTP
                pass
            elif status == 400:
                from main import app
from bot import app
                with app.app_context():
                    rental = Rental.query.get(rental_id)
                    if rental and rental.status == 'waiting':
                        rental.status = 'expired'
                        rental.updated_at = datetime.now()
                        db.session.commit()
                        
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"? **OTP H?T H?N**\n\nS? `{phone}` dã h?t h?n.",
                            parse_mode='Markdown'
                        )
                        return
                        
        except Exception as e:
            logger.error(f"L?i auto-check: {e}")
        
        await asyncio.sleep(5)
    
    logger.info(f"? H?t th?i gian auto-check cho rental {rental_id}")
    await bot.send_message(
        chat_id=chat_id,
        text=f"? **ÐÃ H?T TH?I GIAN CH? OTP**\n\nS? `{phone}` dã h?t h?n.",
        parse_mode='Markdown'
    )

async def rent_view_callback(update: Update, context: Context):
    """Xem chi ti?t s? dã thuê"""
    query = update.callback_query
    await query.answer()
    
    try:
        rental_id = int(query.data.split('_')[2])
    except:
        await query.edit_message_text("? L?i d? li?u")
        return
    
    from main import app
from bot import app
    with app.app_context():
        rental = Rental.query.get(rental_id)
        
        if not rental:
            await query.edit_message_text(
                "? **KHÔNG TÌM TH?Y THÔNG TIN THUÊ S?**\n\n"
                "Có th? s? dã b? xóa ho?c không t?n t?i.",
                parse_mode='Markdown'
            )
            return
        
        expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
        if expires_in < 0:
            expires_in = 0
            
        status_text = {
            'waiting': f'? Ðang ch? OTP (còn {expires_in} phút)',
            'success': '? Ðã nh?n OTP',
            'cancelled': '? Ðã h?y',
            'expired': '? Ðã h?t h?n'
        }.get(rental.status, 'Không xác d?nh')
        
        text = f"""?? **CHI TI?T S? THUÊ**

• **S?:** `{rental.phone_number}`
• **D?ch v?:** {rental.service_name}
• **Giá thuê:** {rental.price_charged:,}d
• **Tr?ng thái:** {status_text}
• **Th?i gian thuê:** {rental.created_at.strftime('%H:%M:%S %d/%m/%Y')}

"""
        keyboard = []
        
        if rental.status == 'waiting':
            if rental.otp_id:
                keyboard.append([InlineKeyboardButton("?? KI?M TRA OTP", callback_data=f"rent_check_{rental.otp_id}_{rental.id}")])
            if rental.sim_id:
                keyboard.append([InlineKeyboardButton("? H?Y S?", callback_data=f"rent_cancel_{rental.sim_id}_{rental.id}")])
        
        if rental.otp_code:
            text += f"? **MÃ OTP:** `{rental.otp_code}`\n"
            if rental.content:
                text += f"?? **N?i dung:** {rental.content}\n"
        
        keyboard.append([InlineKeyboardButton("?? DANH SÁCH S?", callback_data="menu_rent_list")])
        keyboard.append([InlineKeyboardButton("?? QUAY L?I", callback_data="menu_rent")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_cancel_callback(update: Update, context: Context):
    """H?y s? - HOÀN TI?N CHÍNH XÁC"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        sim_id = data[2]
        rental_id = int(data[3])
    except Exception as e:
        logger.error(f"L?i parse cancel: {e}")
        await query.edit_message_text("? **L?I D? LI?U**\n\nVui lòng th? l?i.")
        return
    
    await query.edit_message_text(
        "?? **ÐANG X? LÝ H?Y S?...**\n\n?? Vui lòng ch? trong giây lát.",
        parse_mode='Markdown'
    )
    
    from main import app
from bot import app
    with app.app_context():
        rental = Rental.query.get(rental_id)
        
        if not rental:
            await query.edit_message_text(
                "? **KHÔNG TÌM TH?Y GIAO D?CH**\n\n"
                f"Mã giao d?ch: {rental_id}\n"
                f"Vui lòng ki?m tra l?i ho?c liên h? admin.",
                parse_mode='Markdown'
            )
            return
        
        if rental.status != 'waiting':
            status_text = {
                'success': 'dã nh?n OTP',
                'cancelled': 'dã h?y tru?c dó',
                'expired': 'dã h?t h?n'
            }.get(rental.status, 'dã x? lý')
            
            await query.edit_message_text(
                f"? **KHÔNG TH? H?Y**\n\n"
                f"S? này dã {status_text}.\n"
                f"Không th? h?y và hoàn ti?n.",
                parse_mode='Markdown'
            )
            return
        
        phone = rental.phone_number or "Không xác d?nh"
        service_name = rental.service_name or "Không xác d?nh"
        refund = rental.price_charged  # S? ti?n dã tr? khi thuê
        
        user = User.query.filter_by(user_id=rental.user_id).first()
        
        if not user:
            logger.error(f"? KHÔNG TÌM TH?Y USER v?i user_id={rental.user_id}")
            
            rental.status = 'cancelled'
            rental.updated_at = datetime.now()
            db.session.commit()
            
            keyboard = [
                [InlineKeyboardButton("?? THUÊ TI?P", callback_data="menu_rent")],
                [InlineKeyboardButton("?? MENU CHÍNH", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"?? **H?Y S? THÀNH CÔNG (KHÔNG HOÀN TI?N)**\n\n"
                f"?? **S?:** {phone}\n"
                f"?? **D?ch v?:** {service_name}\n\n"
                f"? **KHÔNG TÌM TH?Y TÀI KHO?N**\n"
                f"Vui lòng liên h? admin d? du?c hoàn ti?n th? công.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        try:
            url = f"{BASE_URL}/sim/cancel_api_key/{sim_id}?api_key={API_KEY}"
            logger.info(f"??? H?y s? sim_id={sim_id}")
            response = requests.get(url, timeout=10)
            api_data = response.json()
            api_success = api_data.get('status') == 200
            
            # C?p nh?t tr?ng thái
            rental.status = 'cancelled'
            rental.updated_at = datetime.now()
            
            # HOÀN L?I ÐÚNG S? TI?N (KHÔNG C?NG THÊM)
            old_balance = user.balance
            user.balance += refund  # Ch? c?ng l?i s? ti?n dã tr?
            
            logger.info(f"?? HOÀN {refund}d CHO USER {user.user_id}")
            logger.info(f"   S? du: {old_balance}d ? {user.balance}d (chênh l?ch: +{refund}d)")
            
            db.session.commit()
            
            keyboard = [
                [InlineKeyboardButton("?? THUÊ TI?P", callback_data="menu_rent")],
                [InlineKeyboardButton("?? XEM S? DU", callback_data="menu_balance")],
                [InlineKeyboardButton("?? MENU CHÍNH", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status_text = "? **H?Y S? THÀNH CÔNG!**" if api_success else "?? **H?Y C?C B? (L?I API)**"
            
            await query.edit_message_text(
                f"{status_text}\n\n"
                f"?? **S?:** {phone}\n"
                f"?? **D?ch v?:** {service_name}\n"
                f"?? **Hoàn ti?n:** {refund:,}d\n"
                f"?? **S? du m?i:** {user.balance:,}d\n\n"
                f"? Ðã hoàn ti?n vào tài kho?n c?a b?n!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"? L?i h?y s?: {e}")
            # X? lý l?i...

async def rent_list_callback(update: Update, context: Context):
    """Hi?n th? danh sách s? dang thuê"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    from main import app
from bot import app
    with app.app_context():
        # L?y t?t c? s? dang waiting
        active_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status == 'waiting',
            Rental.expires_at > datetime.now()
        ).order_by(Rental.created_at.desc()).all()
        
        # L?y s? dã success g?n dây
        recent_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status == 'success'
        ).order_by(Rental.created_at.desc()).limit(5).all()
        
        # L?y s? dã h?y/h?t h?n
        old_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status.in_(['cancelled', 'expired'])
        ).order_by(Rental.created_at.desc()).limit(5).all()
    
    # Xóa menu hi?n t?i
    await query.message.delete()
    
    if not active_rentals and not recent_rentals and not old_rentals:
        keyboard = [[InlineKeyboardButton("?? THUÊ S? NGAY", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="? **B?N CHUA THUÊ S? NÀO**\n\nHãy thuê s? d?u tiên ngay!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    text = "?? **DANH SÁCH S? C?A B?N**\n\n"
    keyboard = []
    
    if active_rentals:
        text += "?? **ÐANG HO?T Ð?NG:**\n"
        for rental in active_rentals:
            expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
            if expires_in < 0:
                expires_in = 0
            text += f"• `{rental.phone_number}` - {rental.service_name} ?{expires_in}p\n"
            keyboard.append([InlineKeyboardButton(
                f"?? {rental.phone_number} - {rental.service_name} (?{expires_in}p)",
                callback_data=f"rent_view_{rental.id}"
            )])
        text += "\n"
    
    if recent_rentals:
        text += "? **ÐÃ NH?N OTP G?N ÐÂY:**\n"
        for rental in recent_rentals:
            text += f"• `{rental.phone_number}` - {rental.service_name} - OTP: `{rental.otp_code}`\n"
        text += "\n"
    
    if old_rentals:
        text += "? **ÐÃ H?T H?N/H?Y:**\n"
        for rental in old_rentals:
            status_icon = "?" if rental.status == 'cancelled' else "?"
            text += f"• {status_icon} `{rental.phone_number}` - {rental.service_name}\n"
    
    keyboard.append([InlineKeyboardButton("? THUÊ S? M?I", callback_data="menu_rent")])
    keyboard.append([InlineKeyboardButton("?? MENU CHÍNH", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
