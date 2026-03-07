import sqlite3
import requests
import time
import os
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

def get_all_users():
    """Lấy danh sách tất cả user từ local"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return users
    except Exception as e:
        print(f"❌ Lỗi lấy danh sách user: {e}")
        return []

def sync_all_users():
    """Đồng bộ tất cả user với Render"""
    users = get_all_users()
    
    if not users:
        print("⚠️ Không có user nào để đồng bộ")
        return
    
    print(f"🔄 Đồng bộ {len(users)} user...")
    
    for user_id in users:
        try:
            response = requests.post(
                f"{RENDER_URL}/api/force-sync-user",
                json={'user_id': user_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                render_balance = data['balance']
                
                # Cập nhật local
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Lấy số dư cũ
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                old = cursor.fetchone()
                old_balance = old[0] if old else 0
                
                # Cập nhật số dư mới
                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (render_balance, user_id))
                
                # Cập nhật trạng thái giao dịch
                for trans in data['transactions']:
                    cursor.execute("""
                        UPDATE transactions 
                        SET status = ?, updated_at = ? 
                        WHERE transaction_code = ?
                    """, (trans['status'], datetime.now(), trans['code']))
                
                conn.commit()
                conn.close()
                
                if old_balance != render_balance:
                    print(f"  ✅ User {user_id}: {old_balance}đ → {render_balance}đ")
            else:
                print(f"  ❌ User {user_id}: Lỗi {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ User {user_id}: {e}")
        
        time.sleep(0.5)  # Tránh spam API

if __name__ == "__main__":
    print("="*60)
    print("🔄 ĐỒNG BỘ TẤT CẢ USER LOCAL ↔ RENDER")
    print("="*60)
    
    sync_all_users()