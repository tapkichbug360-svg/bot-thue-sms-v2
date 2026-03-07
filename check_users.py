import sqlite3
import os

def check_all_users():
    """Kiểm tra tất cả user trong database"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Lấy danh sách user
        cursor.execute('SELECT user_id, username, balance FROM users ORDER BY user_id')
        users = cursor.fetchall()
        
        print("\n📋 DANH SÁCH TẤT CẢ USER")
        print("="*70)
        print(f"{'User ID':<15} {'Username':<20} {'Balance':>15}")
        print("-"*70)
        
        for uid, uname, bal in users:
            print(f"{uid:<15} @{uname:<19} {bal:>15,}đ")
        
        # Thống kê
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        print("="*70)
        print(f"📊 Tổng số user: {total_users}")
        print(f"💰 Tổng số dư: {total_balance:,}đ")
        
        # Kiểm tra giao dịch
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = "pending"')
        pending = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = "success"')
        success = cursor.fetchone()[0]
        
        print(f"📊 Giao dịch pending: {pending}")
        print(f"✅ Giao dịch success: {success}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")

def fix_user_6831611266():
    """Fix user mới bị lỗi"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Kiểm tra user 6831611266
        cursor.execute('SELECT * FROM users WHERE user_id = 6831611266')
        user = cursor.fetchone()
        
        if not user:
            print("❌ Không tìm thấy user 6831611266")
            conn.close()
            return
        
        print(f"📊 User 6831611266 hiện tại:")
        print(f"  ID: {user[0]}")
        print(f"  User ID: {user[1]}")
        print(f"  Username: {user[2]}")
        print(f"  Balance: {user[3]}đ")
        
        # Cập nhật số dư lên 20,000đ
        cursor.execute('UPDATE users SET balance = 20000 WHERE user_id = 6831611266')
        conn.commit()
        
        print("✅ Đã cập nhật số dư user 6831611266 lên 20,000đ")
        conn.close()
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    print("="*70)
    print("🔍 KIỂM TRA DATABASE USER")
    print("="*70)
    print("1. Xem tất cả user")
    print("2. Fix user 6831611266")
    print("3. Thoát")
    print("="*70)
    
    choice = input("Chọn: ").strip()
    
    if choice == "1":
        check_all_users()
    elif choice == "2":
        fix_user_6831611266()
        check_all_users()
    else:
        print("👋 Tạm biệt!")