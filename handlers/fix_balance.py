import sqlite3
import requests
from bot import app
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

def fix_user_balance(user_id):
    """Đồng bộ và sửa số dư user từ Render về local"""
    print(f"\n🔍 Đang xử lý user {user_id}...")
    
    # 1. Lấy từ Render
    try:
        response = requests.post(
            f"{RENDER_URL}/api/force-sync-user",
            json={'user_id': user_id},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Không thể lấy dữ liệu từ Render")
            return
        
        data = response.json()
        render_balance = data['balance']
        render_transactions = data['transactions']
        
        print(f"📊 Render: Balance = {render_balance:,}đ, {len(render_transactions)} transactions")
        
    except Exception as e:
        print(f"❌ Lỗi kết nối Render: {e}")
        return
    
    # 2. Kiểm tra local
    conn = sqlite3.connect('database/bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, balance FROM users WHERE user_id = %s", (user_id,))
    local_user = cursor.fetchone()
    
    if not local_user:
        print(f"❌ User {user_id} không tồn tại trong local")
        conn.close()
        return
    
    local_balance = local_user[1]
    print(f"📊 Local: Balance = {local_balance:,}đ")
    
    # 3. Tính toán số dư đúng từ transactions
    cursor.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = %s AND status = 'success'
    """, (local_user[0],))
    total_success = cursor.fetchone()[0] or 0
    
    print(f"📊 Tổng success trong local: {total_success:,}đ")
    
    # 4. Hiển thị lựa chọn
    print("\n" + "="*50)
    print("LỰA CHỌN:")
    print("1. Cập nhật local theo Render")
    print("2. Giữ local hiện tại")
    print("3. Tính toán lại từ đầu (dùng tổng success)")
    print("4. Force push local lên Render")
    print("="*50)
    
    choice = input("Chọn (1-4): ").strip()
    
    if choice == "1":
        cursor.execute("UPDATE users SET balance = %s WHERE user_id = %s", (render_balance, user_id))
        print(f"✅ Đã cập nhật local balance = {render_balance:,}đ")
    elif choice == "3":
        cursor.execute("UPDATE users SET balance = %s WHERE user_id = %s", (total_success, user_id))
        print(f"✅ Đã cập nhật local balance = {total_success:,}đ")
    elif choice == "4":
        # Push user lên Render
        cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
        username = cursor.fetchone()[0]
        
        push_response = requests.post(
            f"{RENDER_URL}/api/check-user",
            json={'user_id': user_id, 'username': username},
            timeout=5
        )
        print(f"✅ Push user: {push_response.status_code}")
        
        # Push transactions
        cursor.execute("""
            SELECT transaction_code, amount FROM transactions 
            WHERE user_id = %s AND status = 'pending'
        """, (local_user[0],))
        pending = cursor.fetchall()
        
        for code, amt in pending:
            trans_response = requests.post(
                f"{RENDER_URL}/api/sync-pending",
                json={'transactions': [{
                    'code': code,
                    'amount': amt,
                    'user_id': user_id,
                    'username': username
                }]},
                timeout=5
            )
            print(f"  ✅ Push {code}: {trans_response.status_code}")
    else:
        print("✅ Giữ nguyên")
    
    conn.commit()
    conn.close()

def list_all_users():
    """Liệt kê tất cả users"""
    conn = sqlite3.connect('database/bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC")
    users = cursor.fetchall()
    
    print("\n📋 DANH SÁCH USERS:")
    print("="*70)
    for uid, uname, bal in users:
        print(f"  {uid}: @{uname} - {bal:,}đ")
    
    conn.close()

if __name__ == "__main__":
    print("="*70)
    print("🛠️  CÔNG CỤ SỬA SỐ DƯ - ĐỒNG BỘ 2 CHIỀU")
    print("="*70)
    
    list_all_users()
    
    user_id = input("\nNhập user_id cần fix (Enter để thoát): ").strip()
    if user_id:
        fix_user_balance(int(user_id))
        list_all_users()
