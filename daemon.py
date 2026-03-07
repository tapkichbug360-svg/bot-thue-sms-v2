import sqlite3
import requests
import time
import os
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

class UserSyncDaemon:
    def __init__(self):
        self.running = True
        self.user_cache = {}
    
    def get_all_users(self):
        """Lấy danh sách tất cả user từ database local"""
        try:
            db_path = os.path.join('database', 'bot.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id, username, balance FROM users ORDER BY user_id')
            users = cursor.fetchall()
            conn.close()
            
            return [{'user_id': row[0], 'username': row[1], 'balance': row[2]} for row in users]
        except Exception as e:
            print(f"❌ Lỗi lấy danh sách user: {e}")
            return []
    
    def push_user_to_render(self, user_id, username):
        """ĐẨY user mới lên Render"""
        try:
            response = requests.post(
                f"{RENDER_URL}/api/check-user",
                json={'user_id': user_id, 'username': username},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('exists'):
                    print(f"  ✅ User {user_id} đã tồn tại trên Render")
                else:
                    print(f"  ✅ User {user_id} đã được tạo trên Render")
                return True
            else:
                print(f"  ❌ User {user_id}: Lỗi {response.status_code}")
                return False
        except Exception as e:
            print(f"  ❌ User {user_id}: {e}")
            return False
    
    def sync_single_user(self, user_id):
        """Đồng bộ một user (lấy dữ liệu từ Render về)"""
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
                
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                old = cursor.fetchone()
                old_balance = old[0] if old else 0
                
                if old_balance != render_balance:
                    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (render_balance, user_id))
                    print(f"  ✅ User {user_id}: {old_balance}đ → {render_balance}đ")
                
                # Cập nhật giao dịch
                for trans in data['transactions']:
                    cursor.execute("""
                        UPDATE transactions 
                        SET status = ?, updated_at = ? 
                        WHERE transaction_code = ?
                    """, (trans['status'], datetime.now(), trans['code']))
                
                conn.commit()
                conn.close()
                return True
            elif response.status_code == 404:
                # User không tồn tại trên Render -> Cần push lên
                print(f"  ⚠️ User {user_id} không tồn tại trên Render, đang push lên...")
                
                # Lấy username từ local
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                username = result[0] if result else f"user_{user_id}"
                conn.close()
                
                # Push user lên Render
                return self.push_user_to_render(user_id, username)
            else:
                print(f"  ❌ User {user_id}: Lỗi {response.status_code}")
                return False
        except Exception as e:
            print(f"  ❌ User {user_id}: {e}")
            return False
    
    def sync_all_users(self):
        """Đồng bộ tất cả user (2 chiều)"""
        users = self.get_all_users()
        
        if not users:
            print("⚠️ Không có user nào trong database")
            return
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 Bắt đầu đồng bộ {len(users)} user...")
        
        success_count = 0
        for user in users:
            if self.sync_single_user(user['user_id']):
                success_count += 1
            time.sleep(0.2)  # Tránh spam API
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Hoàn tất: {success_count}/{len(users)} user đồng bộ")
    
    def watch_realtime(self):
        """Theo dõi số dư thời gian thực"""
        last_balances = {}
        
        print("👀 THEO DÕI SỐ DƯ THỜI GIAN THỰC - TẤT CẢ USER")
        print("="*70)
        print("Nhấn Ctrl+C để dừng\n")
        
        while self.running:
            try:
                users = self.get_all_users()
                
                for user in users:
                    user_id = user['user_id']
                    current = user['balance']
                    
                    if user_id not in last_balances:
                        last_balances[user_id] = current
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 User {user_id}: {current:,}đ")
                    elif current != last_balances[user_id]:
                        old = last_balances[user_id]
                        change = current - old
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔔 User {user_id}: {old:,}đ → {current:,}đ ({change:+,}đ)")
                        last_balances[user_id] = current
                
                time.sleep(2)
            except KeyboardInterrupt:
                print("\n👋 Đã dừng theo dõi")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Lỗi: {e}")
                time.sleep(5)
    
    def run_daemon(self):
        """Chạy daemon tự động đồng bộ"""
        print("="*70)
        print("🚀 DAEMON ĐỒNG BỘ TẤT CẢ USER - 2 CHIỀU")
        print("⏱️  Đồng bộ mỗi 30 giây")
        print("="*70)
        
        counter = 0
        while self.running:
            try:
                counter += 1
                self.sync_all_users()
                
                if self.running:
                    print(f"\n⏳ Đợi 30 giây đến lần {counter+1}...")
                    for i in range(30):
                        if not self.running:
                            break
                        time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n👋 Đã dừng daemon")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Lỗi daemon: {e}")
                time.sleep(10)
    
    def stop(self):
        self.running = False

def fix_user_balance(user_id, amount):
    """Công cụ sửa số dư thủ công"""
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

if __name__ == "__main__":
    daemon = UserSyncDaemon()
    
    print("="*70)
    print("🔄 CÔNG CỤ ĐỒNG BỘ USER - 2 CHIỀU")
    print("="*70)
    print("1. Đồng bộ một lần tất cả user")
    print("2. Chạy daemon (tự động mỗi 30 giây)")
    print("3. Theo dõi số dư thời gian thực")
    print("4. Sửa số dư user")
    print("5. Push user cụ thể lên Render")
    print("6. Thoát")
    print("="*70)
    
    choice = input("Chọn chức năng (1-6): ").strip()
    
    if choice == "1":
        daemon.sync_all_users()
    elif choice == "2":
        daemon.run_daemon()
    elif choice == "3":
        daemon.watch_realtime()
    elif choice == "4":
        user_id = input("Nhập user_id: ").strip()
        amount = int(input("Nhập số dư mới: ").strip())
        fix_user_balance(int(user_id), amount)
    elif choice == "5":
        user_id = input("Nhập user_id cần push: ").strip()
        username = input("Nhập username: ").strip()
        daemon.push_user_to_render(int(user_id), username)
    else:
        print("👋 Tạm biệt!")