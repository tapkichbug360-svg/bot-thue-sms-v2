import sqlite3
import requests
import time
import os
from datetime import datetime, timedelta

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

class UserSyncDaemon:
    def __init__(self):
        self.running = True
        self.processed_transactions = set()
    
    def get_all_local_users(self):
        """Lấy tất cả user từ database local"""
        try:
            db_path = os.path.join('database', 'bot.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id, username, balance FROM users')
            users = cursor.fetchall()
            conn.close()
            
            return [{'user_id': row[0], 'username': row[1], 'balance': row[2]} for row in users]
        except Exception as e:
            print(f"❌ Lỗi lấy user local: {e}")
            return []
    
    def push_user_to_render(self, user_id, username):
        """Đẩy user lên Render"""
        try:
            response = requests.post(
                f"{RENDER_URL}/api/check-user",
                json={'user_id': user_id, 'username': username},
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            return False
        except Exception as e:
            print(f"  ❌ Lỗi push user {user_id}: {e}")
            return False
    
    def sync_user_from_render(self, user_id):
        """Lấy dữ liệu user từ Render về"""
        try:
            response = requests.post(
                f"{RENDER_URL}/api/force-sync-user",
                json={'user_id': user_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Cập nhật local
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Cập nhật số dư
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                old = cursor.fetchone()
                old_balance = old[0] if old else 0
                
                if old_balance != data['balance']:
                    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (data['balance'], user_id))
                    print(f"  💰 User {user_id}: {old_balance}đ → {data['balance']}đ")
                
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
                # User không tồn tại trên Render, cần push lên
                return False
            return False
        except Exception as e:
            print(f"  ❌ Lỗi sync user {user_id}: {e}")
            return False
    
    def watch_new_transactions(self):
        """Theo dõi giao dịch mới và tự động push user"""
        try:
            db_path = os.path.join('database', 'bot.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Lấy giao dịch mới trong 30 giây qua
            cursor.execute('''
                SELECT t.transaction_code, t.amount, u.user_id, u.username
                FROM transactions t
                JOIN users u ON t.user_id = u.id
                WHERE t.created_at > datetime('now', '-30 seconds')
                ORDER BY t.created_at DESC
            ''')
            
            new_trans = cursor.fetchall()
            conn.close()
            
            for code, amount, uid, username in new_trans:
                if code not in self.processed_transactions:
                    print(f"🆕 Phát hiện giao dịch mới: {code} - {amount}đ - user {uid}")
                    
                    # Push user lên Render
                    if self.push_user_to_render(uid, username):
                        print(f"  ✅ Đã push user {uid} lên Render")
                        self.processed_transactions.add(code)
                    else:
                        print(f"  ❌ Không thể push user {uid}")
                    
        except Exception as e:
            print(f"❌ Lỗi watch transactions: {e}")
    
    def sync_all_users(self):
        """Đồng bộ tất cả user (2 chiều)"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 BẮT ĐẦU ĐỒNG BỘ...")
        
        local_users = self.get_all_local_users()
        print(f"📋 Local có {len(local_users)} user")
        
        success_push = 0
        success_pull = 0
        
        for user in local_users:
            user_id = user['user_id']
            username = user['username'] or f"user_{user_id}"
            
            # Thử lấy dữ liệu từ Render
            if self.sync_user_from_render(user_id):
                success_pull += 1
            else:
                # Nếu không có, push lên Render
                if self.push_user_to_render(user_id, username):
                    print(f"  ✅ User {user_id} đã được push lên Render")
                    success_push += 1
                else:
                    print(f"  ❌ User {user_id} thất bại")
            
            time.sleep(0.2)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Hoàn tất: {success_push} push, {success_pull} pull")
    
    def run_daemon(self):
        """Chạy daemon tự động"""
        print("="*70)
        print("🚀 DAEMON ĐỒNG BỘ TỰ ĐỘNG - 2 CHIỀU")
        print("⏱️  Chạy mỗi 30 giây + theo dõi giao dịch mới")
        print("="*70)
        
        counter = 0
        while self.running:
            try:
                counter += 1
                
                # Đồng bộ tất cả user
                self.sync_all_users()
                
                # Theo dõi giao dịch mới
                self.watch_new_transactions()
                
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

def quick_fix_user(user_id, username, amount, transaction_code):
    """Fix nhanh user bị lỗi"""
    try:
        # Push user lên Render
        requests.post(
            f"{RENDER_URL}/api/check-user",
            json={'user_id': user_id, 'username': username},
            timeout=5
        )
        
        # Cập nhật local
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('''UPDATE transactions SET status = 'success', updated_at = ? WHERE transaction_code = ?''', 
                      (datetime.now(), transaction_code))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Đã fix user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Lỗi fix: {e}")
        return False

if __name__ == "__main__":
    daemon = UserSyncDaemon()
    
    print("="*70)
    print("🔄 CÔNG CỤ ĐỒNG BỘ USER - TỰ ĐỘNG 2 CHIỀU")
    print("="*70)
    print("1. Đồng bộ một lần tất cả user")
    print("2. Chạy daemon (tự động mỗi 30 giây)")
    print("3. Fix user cụ thể")
    print("4. Thoát")
    print("="*70)
    
    choice = input("Chọn (1-4): ").strip()
    
    if choice == "1":
        daemon.sync_all_users()
    elif choice == "2":
        daemon.run_daemon()
    elif choice == "3":
        user_id = int(input("User ID: "))
        username = input("Username: ")
        amount = int(input("Số tiền: "))
        code = input("Mã GD: ")
        quick_fix_user(user_id, username, amount, code)
    else:
        print("👋 Tạm biệt!")