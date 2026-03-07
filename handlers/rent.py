from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from bot import app
from telegram.ext import CallbackContext as Context
from database.models import User, Rental, db
from datetime import datetime, timedelta
import requests
import os
import logging
import time
import asyncio

logger = logging.getLogger(__name__)

API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL')

# Cache để tránh gọi API quá nhiều
services_cache = []
services_cache_time = 0
networks_cache = []
networks_cache_time = 0

async def delete_previous_menu(update: Update, context: Context):
    """Xóa menu trước đó để tránh nhiều menu chồng lên nhau"""
    try:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.delete()
    except Exception as e:
        logger.error(f"Lỗi xóa menu cũ: {e}")

async def get_services():
    """Lấy danh sách dịch vụ từ API"""
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
            logger.error(f"Lỗi API services: {data}")
            return []
    except Exception as e:
        logger.error(f"Lỗi kết nối API services: {e}")
        return []

async def get_networks():
    """Lấy danh sách nhà mạng từ API"""
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
            logger.error(f"Lỗi API networks: {data}")
            return []
    except Exception as e:
        logger.error(f"Lỗi kết nối API networks: {e}")
        return []

async def get_account_info():
    """Lấy thông tin tài khoản API"""
    try:
        url = f"{BASE_URL}/yourself/information-by-api-key?api_key={API_KEY}"
        response = requests.get(url)
        data = response.json()
        if data.get('status') == 200:
            return data.get('data', {})
        return None
    except Exception as e:
        logger.error(f"Lỗi lấy thông tin tài khoản: {e}")
        return None

async def rent_command(update: Update, context: Context):
    """Hiển thị danh sách dịch vụ (đã ẩn số dư API)"""
    logger.info("📱 rent_command được gọi")
    
    # Xóa menu cũ trước khi hiển thị menu mới
    await delete_previous_menu(update, context)
    
    # Kiểm tra user có bị ban không
    user = update.effective_user
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        if db_user and db_user.is_banned:
            text = "❌ **TÀI KHOẢN CỦA BẠN ĐÃ BỊ KHÓA**\n\nVui lòng liên hệ admin để biết thêm chi tiết."
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode='Markdown'
            )
            return
    
    # Hiển thị trạng thái đang tải
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ **ĐANG TẢI DANH SÁCH DỊCH VỤ...**\n\nVui lòng chờ trong giây lát.",
        parse_mode='Markdown'
    )
    
    services = await get_services()
    
    if not services:
        await loading_msg.edit_text(
            "❌ **KHÔNG THỂ LẤY DANH SÁCH DỊCH VỤ**\n\n"
            "• Kiểm tra kết nối API\n"
            "• Thử lại sau vài phút\n"
            "• Liên hệ admin nếu lỗi tiếp diễn",
            parse_mode='Markdown'
        )
        return
    
    # Lọc các dịch vụ bị cấm
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
            "⚠️ **KHÔNG CÓ DỊCH VỤ NÀO KHẢ DỤNG**\n\n"
            "Tất cả dịch vụ hiện đang tạm ngưng.",
            parse_mode='Markdown'
        )
        return
    
    # Tạo keyboard với giá đã cộng 1000đ - HIỂN THỊ TẤT CẢ DỊCH VỤ
    keyboard = []
    row = []
    for i, sv in enumerate(filtered_services):
        try:
            original_price = int(float(sv['price']))
            final_price = original_price + 1000
        except:
            original_price = 1200
            final_price = 2200
            
        button = InlineKeyboardButton(
            f"{sv['name']} - {final_price:,}đ",
            callback_data=f"rent_service_{sv['id']}_{sv['name']}_{original_price}"
        )
        row.append(button)
        
        # 2 nút trên 1 hàng
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Thêm hàng cuối cùng nếu còn
    if row:
        keyboard.append(row)
    
    # Thêm nút điều hướng
    keyboard.append([InlineKeyboardButton("📋 DANH SÁCH SỐ CỦA TÔI", callback_data="menu_rent_list")])
    keyboard.append([InlineKeyboardButton("🔙 QUAY LẠI MENU", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Đếm số dịch vụ
    total_services = len(filtered_services)
    
    text = (
        f"📱 **THUÊ SỐ NHẬN OTP**\n\n"
        f"📊 **Tổng số dịch vụ:** {total_services}\n\n"
        f"⚠️ **TUÂN THỦ PHÁP LUẬT:**\n"
        f"• Nghiêm cấm đánh bạc, cá độ, lừa đảo\n"
        f"• Nghiêm cấm tạo bank ảo, tiền ảo\n"
        f"• Dịch vụ ZALO, Telegram hiện đang CẤM!\n"
        f"• Mọi vi phạm sẽ khóa tài khoản vĩnh viễn\n\n"
        f"👇 **Chọn dịch vụ bên dưới:**"
    )
    
    await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_service_callback(update: Update, context: Context):
    """Xử lý khi chọn dịch vụ"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        service_id = data[2]
        service_name = data[3]
        original_price = int(float(data[4]))
        final_price = original_price + 1000
    except Exception as e:
        logger.error(f"Lỗi parse data: {e}")
        await query.edit_message_text("❌ **LỖI DỮ LIỆU**\n\nVui lòng chọn lại dịch vụ.")
        return
    
    # Lưu thông tin dịch vụ đã chọn
    context.user_data['rent'] = {
        'service_id': service_id,
        'service_name': service_name,
        'final_price': final_price,
        'original_price': original_price
    }
    
    # Xóa menu hiện tại
    try:
        await query.message.delete()
    except:
        pass
    
    # Hiển thị trạng thái đang tải
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ **ĐANG TẢI DANH SÁCH NHÀ MẠNG...**",
        parse_mode='Markdown'
    )
    
    networks = await get_networks()
    
    if not networks:
        keyboard = [[InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.edit_text(
            "❌ **KHÔNG THỂ LẤY DANH SÁCH NHÀ MẠNG**\n\nVui lòng thử lại sau.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Lọc nhà mạng đang hoạt động
    active_networks = [net for net in networks if net.get('status') == 1]
    
    if not active_networks:
        keyboard = [[InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.edit_text(
            "⚠️ **KHÔNG CÓ NHÀ MẠNG NÀO HOẠT ĐỘNG**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for net in active_networks[:10]:
        keyboard.append([InlineKeyboardButton(
            f"📶 {net['name']}",
            callback_data=f"rent_network_{net['id']}_{net['name']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"📱 **{service_name}**\n"
        f"📶 **Chọn nhà mạng:**"
    )
    
    await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_network_callback(update: Update, context: Context):
    """Xử lý khi chọn nhà mạng"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        network_id = data[2]
        network_name = data[3]
    except Exception as e:
        logger.error(f"Lỗi parse network: {e}")
        await query.edit_message_text("❌ **LỖI DỮ LIỆU**\n\nVui lòng chọn lại.")
        return
    
    rent_info = context.user_data.get('rent', {})
    service_id = rent_info.get('service_id')
    service_name = rent_info.get('service_name')
    final_price = rent_info.get('final_price')
    original_price = rent_info.get('original_price')
    
    if not service_id or not final_price:
        await query.edit_message_text("❌ **LỖI!**\n\nVui lòng chọn lại dịch vụ.")
        return
    
    user = update.effective_user
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        current_balance = db_user.balance if db_user else 0
    
    # Xóa menu hiện tại
    await query.message.delete()
    
    keyboard = [
        [InlineKeyboardButton("✅ XÁC NHẬN THUÊ", callback_data=f"rent_confirm_{service_id}_{final_price}_{network_id}")],
        [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"📱 **XÁC NHẬN THUÊ SỐ**\n\n"
        f"• **Dịch vụ:** {service_name}\n"
        f"• **Nhà mạng:** {network_name}\n"
        f"• **Số dư của bạn:** {current_balance:,}đ\n\n"
        f"📌 **Lưu ý:**\n"
        f"• Số tiền sẽ được trừ ngay sau khi xác nhận\n"
        f"• Có thể hủy và được hoàn tiền nếu chưa nhận OTP\n"
        f"• Số có hiệu lực trong 5 phút\n\n"
        f"❓ **Xác nhận thuê số?**"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def rent_confirm_callback(update: Update, context: Context):
    """Xác nhận thuê số - Gọi API lấy số"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        service_id = data[2]
        final_price = int(data[3])
        network_id = data[4]
    except Exception as e:
        logger.error(f"Lỗi parse confirm: {e}")
        await query.edit_message_text("❌ **LỖI DỮ LIỆU**\n\nVui lòng chọn lại.")
        return
    
    user = update.effective_user
    
    with app.app_context():
        db_user = User.query.filter_by(user_id=user.id).first()
        
        if not db_user:
            await query.edit_message_text("❌ **KHÔNG TÌM THẤY TÀI KHOẢN**\n\nVui lòng gửi /start để đăng ký.")
            return
        
        if db_user.balance < final_price:
            shortage = final_price - db_user.balance
            keyboard = [
                [InlineKeyboardButton("💳 NẠP TIỀN NGAY", callback_data="menu_deposit")],
                [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ **SỐ DƯ KHÔNG ĐỦ!**\n\n"
                f"• **Cần:** {final_price:,}đ\n"
                f"• **Có:** {db_user.balance:,}đ\n"
                f"• **Thiếu:** {shortage:,}đ\n\n"
                f"Vui lòng nạp thêm tiền để tiếp tục.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Xóa menu hiện tại
        await query.message.delete()
        
        loading_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ **ĐANG XỬ LÝ YÊU CẦU...**\n\n🤖 Vui lòng chờ trong giây lát.",
            parse_mode='Markdown'
        )
        
        try:
            url = f"{BASE_URL}/sim/get_sim"
            
            # Tạo params
            params = {
                'api_key': API_KEY,
                'service_id': service_id
            }
            
            # Thêm network_id nếu có
            if network_id and network_id != 'None':
                params['network_id'] = network_id
            
            logger.info(f"📞 Gọi API lấy số: service_id={service_id}, network_id={network_id}")
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
                
                logger.info(f"✅ User {user.id} thuê số {phone} thành công")
                logger.info(f"💰 Đã trừ {final_price}đ (từ {old_balance}đ còn {db_user.balance}đ)")
                
                # Lưu rental vào context
                if 'active_rentals' not in context.user_data:
                    context.user_data['active_rentals'] = []
                context.user_data['active_rentals'].append({
                    'id': rental.id,
                    'phone': phone,
                    'service': rent_info['service_name'],
                    'expires_at': rental.expires_at.isoformat()
                })
                
                keyboard = [
                    [InlineKeyboardButton(f"📞 {phone} - {rent_info['service_name']}", callback_data=f"rent_view_{rental.id}")],
                    [InlineKeyboardButton("📋 DANH SÁCH SỐ", callback_data="menu_rent_list")],
                    [InlineKeyboardButton("🆕 THUÊ SỐ KHÁC", callback_data="menu_rent")],
                    [InlineKeyboardButton("🔙 MENU CHÍNH", callback_data="menu_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                text = (
                    f"✅ **THUÊ SỐ THÀNH CÔNG!**\n\n"
                    f"📞 **Số:** `{phone}`\n"
                    f"📱 **Dịch vụ:** {rent_info['service_name']}\n"
                    f"💰 **Đã thanh toán:** {final_price:,}đ\n"
                    f"💵 **Số dư còn lại:** {db_user.balance:,}đ\n"
                    f"⏰ **Hết hạn lúc:** {rental.expires_at.strftime('%H:%M:%S')}\n\n"
                    f"🤖 **TỰ ĐỘNG KIỂM TRA OTP**\n"
                    f"• Bot sẽ tự động kiểm tra và báo khi có OTP\n"
                    f"• Bạn có thể theo dõi số qua menu trên"
                )
                
                await loading_msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
                # Bắt đầu tự động kiểm tra OTP
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
                error_msg = response_data.get('message', 'Không rõ lỗi')
                await loading_msg.edit_text(
                    f"❌ **LỖI TỪ MÁY CHỦ**\n\n"
                    f"📢 Thông báo: {error_msg}\n\n"
                    f"Vui lòng thử lại sau hoặc chọn dịch vụ khác.",
                    parse_mode='Markdown'
                )
                
        except requests.exceptions.Timeout:
            await loading_msg.edit_text(
                "⏰ **TIMEOUT - MÁY CHỦ KHÔNG PHẢN HỒI**\n\n"
                "Vui lòng thử lại sau.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Lỗi thuê số: {e}")
            import traceback
            traceback.print_exc()
            await loading_msg.edit_text(
                "❌ **LỖI KẾT NỐI**\n\n"
                "Vui lòng thử lại sau.",
                parse_mode='Markdown'
            )

async def rent_check_callback(update: Update, context: Context):
    """Kiểm tra OTP thủ công - GỬI FILE AUDIO NẾU CÓ"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        otp_id = data[2]
        rental_id = int(data[3])
    except Exception as e:
        logger.error(f"Lỗi parse check: {e}")
        await query.edit_message_text("❌ **LỖI DỮ LIỆU**\n\nVui lòng thử lại.")
        return
    
    # Hiển thị trạng thái đang kiểm tra
    await query.edit_message_text(
        "⏳ **ĐANG KIỂM TRA OTP...**\n\nVui lòng chờ trong giây lát.",
        parse_mode='Markdown'
    )
    
    try:
        # Gọi API kiểm tra OTP
        url = f"{BASE_URL}/otp/get_otp_by_phone_api_key"
        params = {
            'api_key': API_KEY,
            'otp_id': otp_id
        }
        
        logger.info(f"🔍 Kiểm tra OTP cho otp_id={otp_id}")
        response = requests.get(url, params=params, timeout=10)
        response_data = response.json()
        
        logger.info(f"API check OTP response: {response_data}")
        
        with app.app_context():
            rental = Rental.query.get(rental_id)
            
            if not rental:
                await query.edit_message_text(
                    "❌ **KHÔNG TÌM THẤY THÔNG TIN THUÊ SỐ**\n\n"
                    "Vui lòng thử lại hoặc liên hệ admin.",
                    parse_mode='Markdown'
                )
                return
            
            status = response_data.get('status')
            
            if status == 200:
                otp_data = response_data.get('data', {})
                otp_code = otp_data.get('code')
                content = otp_data.get('content', '')
                sender = otp_data.get('senderName', '')
                audio_url = otp_data.get('audio')  # URL file audio cuộc gọi
                
                # Cập nhật trạng thái rental
                rental.status = 'success'
                rental.otp_code = otp_code or "Audio OTP"
                rental.content = content
                rental.updated_at = datetime.now()
                db.session.commit()
                
                # === XỬ LÝ AUDIO ===
                if audio_url:
                    try:
                        logger.info(f"🎵 Đang tải audio từ: {audio_url}")
                        
                        # Tải file audio
                        audio_response = requests.get(audio_url, timeout=15)
                        
                        if audio_response.status_code == 200:
                            # Xác định định dạng file
                            content_type = audio_response.headers.get('content-type', 'audio/mpeg')
                            file_ext = 'mp3'
                            if 'wav' in content_type:
                                file_ext = 'wav'
                            elif 'ogg' in content_type:
                                file_ext = 'ogg'
                            
                            # Gửi file audio trực tiếp
                            await context.bot.send_audio(
                                chat_id=update.effective_chat.id,
                                audio=audio_response.content,
                                filename=f"otp_call_{rental_id}.{file_ext}",
                                title=f"📞 Cuộc gọi OTP từ {rental.service_name}",
                                caption=(
                                    f"📞 **CUỘC GỌI OTP**\n\n"
                                    f"• **Dịch vụ:** {rental.service_name}\n"
                                    f"• **Số điện thoại:** `{rental.phone_number}`\n"
                                    f"• **Thời gian:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
                                    f"▶️ **Bấm play để nghe lại cuộc gọi**"
                                ),
                                parse_mode='Markdown'
                            )
                            logger.info(f"✅ Đã gửi file audio cuộc gọi cho rental {rental_id}")
                            
                        else:
                            logger.error(f"❌ Không thể tải audio, status code: {audio_response.status_code}")
                            # Gửi link nếu không tải được
                            keyboard = [[InlineKeyboardButton("🎵 NGHE OTP TRÊN WEB", url=audio_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=(
                                    f"📞 **CÓ OTP DẠNG CUỘC GỌI**\n\n"
                                    f"• **Dịch vụ:** {rental.service_name}\n"
                                    f"• **Số:** `{rental.phone_number}`\n\n"
                                    f"❌ Không thể tải file audio tự động.\n"
                                    f"👇 Bấm nút bên dưới để nghe trên web:"
                                ),
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            )
                            
                    except Exception as e:
                        logger.error(f"❌ Lỗi xử lý audio: {e}")
                        # Gửi link dự phòng
                        keyboard = [[InlineKeyboardButton("🎵 NGHE OTP", url=audio_url)]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=(
                                f"📞 **CÓ OTP DẠNG CUỘC GỌI**\n\n"
                                f"• **Dịch vụ:** {rental.service_name}\n"
                                f"• **Số:** `{rental.phone_number}`\n\n"
                                f"👇 Bấm nút để nghe trên web:"
                            ),
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                
                # === GỬI OTP DẠNG TEXT NẾU CÓ ===
                if otp_code:
                    text_message = (
                        f"✅ **NHẬN OTP THÀNH CÔNG!**\n\n"
                        f"🔑 **Mã OTP:** `{otp_code}`\n"
                        f"📝 **Nội dung:** {content}\n"
                        f"👤 **Người gửi:** {sender}\n"
                        f"📱 **Dịch vụ:** {rental.service_name}\n"
                        f"📞 **Số:** `{rental.phone_number}`"
                    )
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=text_message,
                        parse_mode='Markdown'
                    )
                elif not audio_url:
                    # Không có cả audio và text
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"✅ **ĐÃ NHẬN OTP**\n\n📱 **Dịch vụ:** {rental.service_name}\n📞 **Số:** `{rental.phone_number}`",
                        parse_mode='Markdown'
                    )
                
                # Xóa menu cũ
                await query.delete_message()
                
            elif status == 202:
                # Chưa có OTP
                expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
                await query.edit_message_text(
                    f"⏳ **CHƯA CÓ OTP**\n\n"
                    f"• **Số:** `{rental.phone_number}`\n"
                    f"• **Dịch vụ:** {rental.service_name}\n"
                    f"• **Còn:** {expires_in} phút\n\n"
                    f"Vui lòng thử lại sau vài giây.",
                    parse_mode='Markdown'
                )
                
            elif status == 312:
                await query.edit_message_text(
                    f"⏳ **ĐANG CHỜ OTP**\n\n"
                    f"• **Số:** `{rental.phone_number}`\n"
                    f"• **Dịch vụ:** {rental.service_name}",
                    parse_mode='Markdown'
                )
                
            elif status == 400:
                rental.status = 'expired'
                rental.updated_at = datetime.now()
                db.session.commit()
                
                await query.edit_message_text(
                    f"⏰ **OTP ĐÃ HẾT HẠN**\n\n"
                    f"Số `{rental.phone_number}` đã hết hạn.\n"
                    f"Vui lòng thuê số mới.",
                    parse_mode='Markdown'
                )
                
            else:
                error_msg = response_data.get('message', 'Không xác định')
                await query.edit_message_text(
                    f"❌ **LỖI KIỂM TRA OTP**\n\n"
                    f"Lỗi: {error_msg}\n\n"
                    f"Vui lòng thử lại sau.",
                    parse_mode='Markdown'
                )
                
    except requests.exceptions.Timeout:
        await query.edit_message_text(
            "⏰ **TIMEOUT - MÁY CHỦ KHÔNG PHẢN HỒI**\n\n"
            "Vui lòng thử lại sau.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Lỗi kiểm tra OTP: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            "❌ **LỖI KẾT NỐI**\n\n"
            "Vui lòng thử lại sau.",
            parse_mode='Markdown'
        )

async def auto_check_otp_task(bot, chat_id: int, otp_id: str, rental_id: int, user_id: int, service_name: str, phone: str):
    """Tự động kiểm tra OTP - GỬI FILE AUDIO KHI CÓ CUỘC GỌI"""
    logger.info(f"🤖 Bắt đầu auto-check OTP cho rental {rental_id}")
    
    max_checks = 60
    check_count = 0
    
    while check_count < max_checks:
        check_count += 1
        logger.info(f"🔄 Auto-check OTP lần {check_count}/{max_checks} cho rental {rental_id}")
        
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
                audio_url = otp_data.get('audio')  # URL file audio cuộc gọi
                
                with app.app_context():
                    rental = Rental.query.get(rental_id)
                    if rental and rental.status == 'waiting':
                        rental.status = 'success'
                        rental.otp_code = otp_code or "Gọi điện"
                        rental.content = content
                        rental.updated_at = datetime.now()
                        db.session.commit()
                        
                        logger.info(f"✅ Auto-check: Nhận OTP cho rental {rental_id}")
                        
                        # === GỬI FILE AUDIO CUỘC GỌI ===
                        if audio_url:
                            try:
                                logger.info(f"🎵 Đang tải audio cuộc gọi từ: {audio_url}")
                                
                                # Tải file audio
                                audio_response = requests.get(audio_url, timeout=15)
                                
                                if audio_response.status_code == 200:
                                    # Xác định định dạng file
                                    content_type = audio_response.headers.get('content-type', 'audio/mpeg')
                                    file_ext = 'mp3'  # Mặc định
                                    if 'wav' in content_type:
                                        file_ext = 'wav'
                                    elif 'ogg' in content_type:
                                        file_ext = 'ogg'
                                    
                                    # Gửi file audio lên Telegram
                                    await bot.send_audio(
                                        chat_id=chat_id,
                                        audio=audio_response.content,
                                        filename=f"otp_call_{rental_id}.{file_ext}",
                                        title=f"📞 Cuộc gọi OTP từ {service_name}",
                                        caption=(
                                            f"📞 **CUỘC GỌI OTP**\n\n"
                                            f"• **Dịch vụ:** {service_name}\n"
                                            f"• **Số điện thoại:** `{phone}`\n"
                                            f"• **Thời gian:** {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
                                            f"▶️ **Bấm play để nghe lại cuộc gọi**"
                                        ),
                                        parse_mode='Markdown'
                                    )
                                    logger.info(f"✅ Đã gửi file audio cuộc gọi cho rental {rental_id}")
                                    
                                    # Gửi thêm OTP text nếu có
                                    if otp_code:
                                        await bot.send_message(
                                            chat_id=chat_id,
                                            text=f"🔑 **MÃ OTP:** `{otp_code}`\n📝 {content}",
                                            parse_mode='Markdown'
                                        )
                                        
                                else:
                                    logger.error(f"❌ Không thể tải audio, status code: {audio_response.status_code}")
                                    # Fallback: gửi link nếu không tải được
                                    keyboard = [[InlineKeyboardButton("🎵 NGHE OTP TRÊN WEB", url=audio_url)]]
                                    reply_markup = InlineKeyboardMarkup(keyboard)
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=(
                                            f"📞 **CÓ OTP DẠNG CUỘC GỌI**\n\n"
                                            f"• **Dịch vụ:** {service_name}\n"
                                            f"• **Số:** `{phone}`\n\n"
                                            f"❌ Không thể tải file audio tự động.\n"
                                            f"👇 Bấm nút bên dưới để nghe trên web:"
                                        ),
                                        reply_markup=reply_markup,
                                        parse_mode='Markdown'
                                    )
                                    
                            except Exception as e:
                                logger.error(f"❌ Lỗi xử lý audio: {e}")
                                # Fallback
                                keyboard = [[InlineKeyboardButton("🎵 NGHE OTP", url=audio_url)]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=f"📞 **CÓ OTP DẠNG CUỘC GỌI**\n\n👇 Bấm nút để nghe:",
                                    reply_markup=reply_markup,
                                    parse_mode='Markdown'
                                )
                        
                        # Nếu không có audio, chỉ gửi text
                        elif otp_code:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=f"🔑 **MÃ OTP:** `{otp_code}`\n📝 {content}",
                                parse_mode='Markdown'
                            )
                        
                        return
                        
            elif status in [202, 312]:
                # Đang chờ OTP
                pass
            elif status == 400:
                with app.app_context():
                    rental = Rental.query.get(rental_id)
                    if rental and rental.status == 'waiting':
                        rental.status = 'expired'
                        rental.updated_at = datetime.now()
                        db.session.commit()
                        
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"⏰ **OTP HẾT HẠN**\n\nSố `{phone}` đã hết hạn.",
                            parse_mode='Markdown'
                        )
                        return
                        
        except Exception as e:
            logger.error(f"Lỗi auto-check: {e}")
        
        await asyncio.sleep(5)
    
    logger.info(f"⏰ Hết thời gian auto-check cho rental {rental_id}")
    await bot.send_message(
        chat_id=chat_id,
        text=f"⏰ **ĐÃ HẾT THỜI GIAN CHỜ OTP**\n\nSố `{phone}` đã hết hạn.",
        parse_mode='Markdown'
    )

async def rent_view_callback(update: Update, context: Context):
    """Xem chi tiết số đã thuê"""
    query = update.callback_query
    await query.answer()
    
    try:
        rental_id = int(query.data.split('_')[2])
    except:
        await query.edit_message_text("❌ Lỗi dữ liệu")
        return
    
    with app.app_context():
        rental = Rental.query.get(rental_id)
        
        if not rental:
            await query.edit_message_text(
                "❌ **KHÔNG TÌM THẤY THÔNG TIN THUÊ SỐ**\n\n"
                "Có thể số đã bị xóa hoặc không tồn tại.",
                parse_mode='Markdown'
            )
            return
        
        expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
        if expires_in < 0:
            expires_in = 0
            
        status_text = {
            'waiting': f'⏳ Đang chờ OTP (còn {expires_in} phút)',
            'success': '✅ Đã nhận OTP',
            'cancelled': '❌ Đã hủy',
            'expired': '⏰ Đã hết hạn'
        }.get(rental.status, 'Không xác định')
        
        text = f"""📱 **CHI TIẾT SỐ THUÊ**

• **Số:** `{rental.phone_number}`
• **Dịch vụ:** {rental.service_name}
• **Giá thuê:** {rental.price_charged:,}đ
• **Trạng thái:** {status_text}
• **Thời gian thuê:** {rental.created_at.strftime('%H:%M:%S %d/%m/%Y')}

"""
        keyboard = []
        
        if rental.status == 'waiting':
            if rental.otp_id:
                keyboard.append([InlineKeyboardButton("🔍 KIỂM TRA OTP", callback_data=f"rent_check_{rental.otp_id}_{rental.id}")])
            if rental.sim_id:
                keyboard.append([InlineKeyboardButton("❌ HỦY SỐ", callback_data=f"rent_cancel_{rental.sim_id}_{rental.id}")])
        
        if rental.otp_code:
            text += f"🔑 **MÃ OTP:** `{rental.otp_code}`\n"
            if rental.content:
                text += f"📝 **Nội dung:** {rental.content}\n"
        
        keyboard.append([InlineKeyboardButton("📋 DANH SÁCH SỐ", callback_data="menu_rent_list")])
        keyboard.append([InlineKeyboardButton("🔙 QUAY LẠI", callback_data="menu_rent")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def rent_cancel_callback(update: Update, context: Context):
    """Hủy số - HOÀN TIỀN CHÍNH XÁC"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split('_')
        sim_id = data[2]
        rental_id = int(data[3])
    except Exception as e:
        logger.error(f"Lỗi parse cancel: {e}")
        await query.edit_message_text("❌ **LỖI DỮ LIỆU**\n\nVui lòng thử lại.")
        return
    
    await query.edit_message_text(
        "⏳ **ĐANG XỬ LÝ HỦY SỐ...**\n\n🤖 Vui lòng chờ trong giây lát.",
        parse_mode='Markdown'
    )
    
    with app.app_context():
        rental = Rental.query.get(rental_id)
        
        if not rental:
            await query.edit_message_text(
                "❌ **KHÔNG TÌM THẤY GIAO DỊCH**\n\n"
                f"Mã giao dịch: {rental_id}\n"
                f"Vui lòng kiểm tra lại hoặc liên hệ admin.",
                parse_mode='Markdown'
            )
            return
        
        if rental.status != 'waiting':
            status_text = {
                'success': 'đã nhận OTP',
                'cancelled': 'đã hủy trước đó',
                'expired': 'đã hết hạn'
            }.get(rental.status, 'đã xử lý')
            
            await query.edit_message_text(
                f"❌ **KHÔNG THỂ HỦY**\n\n"
                f"Số này đã {status_text}.\n"
                f"Không thể hủy và hoàn tiền.",
                parse_mode='Markdown'
            )
            return
        
        phone = rental.phone_number or "Không xác định"
        service_name = rental.service_name or "Không xác định"
        refund = rental.price_charged  # Số tiền đã trừ khi thuê
        
        user = User.query.filter_by(user_id=rental.user_id).first()
        
        if not user:
            logger.error(f"❌ KHÔNG TÌM THẤY USER với user_id={rental.user_id}")
            
            rental.status = 'cancelled'
            rental.updated_at = datetime.now()
            db.session.commit()
            
            keyboard = [
                [InlineKeyboardButton("🆕 THUÊ TIẾP", callback_data="menu_rent")],
                [InlineKeyboardButton("🔙 MENU CHÍNH", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ **HỦY SỐ THÀNH CÔNG (KHÔNG HOÀN TIỀN)**\n\n"
                f"📞 **Số:** {phone}\n"
                f"📱 **Dịch vụ:** {service_name}\n\n"
                f"❌ **KHÔNG TÌM THẤY TÀI KHOẢN**\n"
                f"Vui lòng liên hệ admin để được hoàn tiền thủ công.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        try:
            url = f"{BASE_URL}/sim/cancel_api_key/{sim_id}?api_key={API_KEY}"
            logger.info(f"❌ Hủy số sim_id={sim_id}")
            response = requests.get(url, timeout=10)
            api_data = response.json()
            api_success = api_data.get('status') == 200
            
            # Cập nhật trạng thái
            rental.status = 'cancelled'
            rental.updated_at = datetime.now()
            
            # HOÀN LẠI ĐÚNG SỐ TIỀN (KHÔNG CỘNG THÊM)
            old_balance = user.balance
            user.balance += refund  # Chỉ cộng lại số tiền đã trừ
            
            logger.info(f"💰 HOÀN {refund}đ CHO USER {user.user_id}")
            logger.info(f"   Số dư trước khi hủy: {old_balance}đ → Sau khi hủy: {user.balance}đ (Hoàn: +{refund}đ)")
            
            db.session.commit()
            
            keyboard = [
                [InlineKeyboardButton("🆕 THUÊ TIẾP", callback_data="menu_rent")],
                [InlineKeyboardButton("💰 XEM SỐ DƯ", callback_data="menu_balance")],
                [InlineKeyboardButton("🔙 MENU CHÍNH", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status_text = "✅ **HỦY SỐ THÀNH CÔNG!**" if api_success else "⚠️ **HỦY CỤC BỘ (LỖI API)**"
            
            await query.edit_message_text(
                f"{status_text}\n\n"
                f"📞 **Số:** {phone}\n"
                f"📱 **Dịch vụ:** {service_name}\n"
                f"💰 **Hoàn tiền:** {refund:,}đ\n"
                f"💵 **Số dư mới:** {user.balance:,}đ\n\n"
                f"✅ Đã hoàn tiền vào tài khoản của bạn!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Lỗi hủy số: {e}")
            # Xử lý lỗi...

async def rent_list_callback(update: Update, context: Context):
    """Hiển thị danh sách số đang thuê"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    with app.app_context():
        # Lấy tất cả số đang waiting
        active_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status == 'waiting',
            Rental.expires_at > datetime.now()
        ).order_by(Rental.created_at.desc()).all()
        
        # Lấy số đã success gần đây
        recent_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status == 'success'
        ).order_by(Rental.created_at.desc()).limit(5).all()
        
        # Lấy số đã hủy/hết hạn
        old_rentals = Rental.query.filter(
            Rental.user_id == user.id,
            Rental.status.in_(['cancelled', 'expired'])
        ).order_by(Rental.created_at.desc()).limit(5).all()
    
    # Xóa menu hiện tại
    await query.message.delete()
    
    if not active_rentals and not recent_rentals and not old_rentals:
        keyboard = [[InlineKeyboardButton("📱 THUÊ SỐ NGAY", callback_data="menu_rent")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📭 **BẠN CHƯA THUÊ SỐ NÀO**\n\nHãy thuê số đầu tiên ngay!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    text = "📋 **DANH SÁCH SỐ CỦA BẠN**\n\n"
    keyboard = []
    
    if active_rentals:
        text += "🟢 **ĐANG HOẠT ĐỘNG:**\n"
        for rental in active_rentals:
            expires_in = int((rental.expires_at - datetime.now()).total_seconds() / 60)
            if expires_in < 0:
                expires_in = 0
            text += f"• `{rental.phone_number}` - {rental.service_name} ⏳{expires_in}p\n"
            keyboard.append([InlineKeyboardButton(
                f"📞 {rental.phone_number} - {rental.service_name} (⏳{expires_in}p)",
                callback_data=f"rent_view_{rental.id}"
            )])
        text += "\n"
    
    if recent_rentals:
        text += "✅ **ĐÃ NHẬN OTP GẦN ĐÂY:**\n"
        for rental in recent_rentals:
            text += f"• `{rental.phone_number}` - {rental.service_name} - OTP: `{rental.otp_code}`\n"
        text += "\n"
    
    if old_rentals:
        text += "⏰ **ĐÃ HẾT HẠN/HỦY:**\n"
        for rental in old_rentals:
            status_icon = "❌" if rental.status == 'cancelled' else "⏰"
            text += f"• {status_icon} `{rental.phone_number}` - {rental.service_name}\n"
    
    keyboard.append([InlineKeyboardButton("🆕 THUÊ SỐ MỚI", callback_data="menu_rent")])
    keyboard.append([InlineKeyboardButton("🔙 MENU CHÍNH", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
