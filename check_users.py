import sqlite3
import os
from datetime import datetime

def get_all_users():
    """Lấy danh sách tất cả user"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.user_id, u.username, u.balance, 
                   COUNT(t.id) as total_trans,
                   SUM(CASE WHEN t.status = 'success' THEN t.amount ELSE 0 END) as total_deposit
            FROM users u
            LEFT JOIN transactions t ON u.id = t.user_id
            GROUP BY u.id
            ORDER BY u.user_id
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        return users
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return []

def fix_user_balance(user_id, amount):
    """Sửa số dư user thủ công"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        old = cursor.fetchone()
        old_balance = old[0] if old else 0
        
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        
        print(f"✅ Đã sửa user {user_id}: {old_balance}đ → {amount}đ")
        return True
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False

def delete_fake_user(user_id):
    """Xóa user ảo (nếu có)"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Đã xóa user ảo {user_id}")
        return True
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False

def main():
    print("="*80)
    print("🔍 QUẢN LÝ USER - HỆ THỐNG THUÊ SMS")
    print("="*80)
    
    users = get_all_users()
    
    if not users:
        print("❌ Không có user nào trong database")
        return
    
    print(f"\n📋 DANH SÁCH {len(users)} USER:")
    print("-"*80)
    print(f"{'User ID':<15} {'Username':<20} {'Balance':>12} {'Giao dịch':>10} {'Tổng nạp':>12}")
    print("-"*80)
    
    for uid, uname, bal, total_trans, total_deposit in users:
        print(f"{uid:<15} @{uname:<19} {bal:>12,}đ {total_trans:>10} {total_deposit:>12,}đ")
    
    print("="*80)
    print("1. Sửa số dư user")
    print("2. Xóa user ảo")
    print("3. Thoát")
    print("="*80)
    
    choice = input("Chọn: ").strip()
    
    if choice == "1":
        uid = int(input("Nhập user_id: "))
        amount = int(input("Nhập số dư mới: "))
        fix_user_balance(uid, amount)
    elif choice == "2":
        uid = int(input("Nhập user_id ảo cần xóa: "))
        delete_fake_user(uid)
    else:
        print("👋 Tạm biệt!")

if __name__ == "__main__":
    main()