import sqlite3
import requests
from datetime import datetime

def fix_user_balance(user_id):
    """Đồng bộ và sửa số dư user"""
    
    print(f"🔍 Đang lấy dữ liệu user {user_id} từ Render...")
    response = requests.post(
        "https://bot-thue-sms-v2.onrender.com/api/force-sync-user",
        json={'user_id': user_id}
    )
    
    if response.status_code != 200:
        print(f"❌ Không thể lấy dữ liệu từ Render")
        return
    
    data = response.json()
    render_balance = data['balance']
    render_transactions = data['transactions']
    
    print(f"📊 Render: Balance = {render_balance:,}đ, {len(render_transactions)} transactions")
    
    conn = sqlite3.connect('database/bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, balance FROM users WHERE user_id = ?", (user_id,))
    local_user = cursor.fetchone()
    
    if not local_user:
        print(f"❌ User {user_id} không tồn tại trong local")
        conn.close()
        return
    
    local_balance = local_user[1]
    print(f"📊 Local: Balance = {local_balance:,}đ")
    
    cursor.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = ? AND status = 'success'
    """, (local_user[0],))
    total_success = cursor.fetchone()[0] or 0
    
    print(f"📊 Tổng success trong local: {total_success:,}đ")
    
    print("\n" + "="*50)
    print("LỰA CHỌN:")
    print("1. Cập nhật local theo Render")
    print("2. Giữ local hiện tại")
    print("3. Tính toán lại từ đầu (dùng tổng success)")
    
    choice = input("Chọn (1/2/3): ").strip()
    
    if choice == "1":
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (render_balance, user_id))
        conn.commit()
        print(f"✅ Đã cập nhật local balance = {render_balance:,}đ")
    elif choice == "3":
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (total_success, user_id))
        conn.commit()
        print(f"✅ Đã cập nhật local balance = {total_success:,}đ")
    else:
        print("✅ Giữ nguyên")
    
    conn.close()

def list_all_users():
    """Liệt kê tất cả users"""
    conn = sqlite3.connect('database/bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC")
    users = cursor.fetchall()
    
    print("\n📋 DANH SÁCH USERS:")
    print("="*60)
    for uid, uname, bal in users:
        print(f"  {uid}: @{uname} - {bal:,}đ")
    
    conn.close()

if __name__ == "__main__":
    print("="*60)
    print("🛠️  CÔNG CỤ SỬA SỐ DƯ")
    print("="*60)
    
    list_all_users()
    
    user_id = input("\nNhập user_id cần fix (Enter để thoát): ").strip()
    if user_id:
        fix_user_balance(int(user_id))