import sqlite3
import requests
import time
import os
from datetime import datetime, timedelta

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

class UserSyncDaemon:
    def __init__(self):
        self.running = True
        self.last_sync = {}
    
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
    
    def get_all_local_transactions(self):
        """Lấy tất cả transaction pending từ local"""
        try:
            db_path = os.path.join('database', 'bot.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.transaction_code, t.amount, u.user_id, u.username
                FROM transactions t
                JOIN users u ON t.user_id = u.id
                WHERE t.status = 'pending'
            """)
            
            pending = cursor.fetchall()
            conn.close()
            
            return [{
                'code': code, 
                'amount': amount, 
                'user_id': uid, 
                'username': username
            } for code, amount, uid, username in pending]
        except Exception as e:
            print(f"❌ Lỗi lấy transaction local: {e}")
            return []
    
    def push_user_to_render(self, user_id, username):
        """Đẩy user lên Render"""
        try:
            response = requests.post(
                f"{RENDER_URL}/api/check-user",
                json={'user_id': user_id, 'username': username},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"  ❌ Lỗi push user {user_id}: {e}")
            return False
    
    def push_transaction_to_render(self, transaction):
        """Đẩy transaction lên Render"""
        try:
            response = requests.post(
                f"{RENDER_URL}/api/sync-pending",
                json={'transactions': [transaction]},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"  ❌ Lỗi push transaction {transaction['code']}: {e}")
            return False
    
    def pull_user_from_render(self, user_id):
        """Kéo user từ Render về"""
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
                
                # Cập nhật số dư
                if old_balance != render_balance:
                    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (render_balance, user_id))
                    print(f"  💰 User {user_id}: {old_balance}đ → {render_balance}đ")
                
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
            return False
        except Exception as e:
            print(f"  ❌ Lỗi pull user {user_id}: {e}")
            return False
    
    def sync_all_users(self):
        """Đồng bộ tất cả user (2 chiều)"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 ĐỒNG BỘ USER 2 CHIỀU...")
        
        local_users = self.get_all_local_users()
        print(f"📋 Local có {len(local_users)} user")
        
        # PUSH: Đẩy user local lên Render
        for user in local_users:
            if self.push_user_to_render(user['user_id'], user['username']):
                print(f"  ✅ Push user {user['user_id']}")
            time.sleep(0.2)
        
        # PULL: Kéo user từ Render về
        for user in local_users:
            self.pull_user_from_render(user['user_id'])
            time.sleep(0.2)
    
    def sync_transactions(self):
        """Đồng bộ tất cả transaction"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 ĐỒNG BỘ TRANSACTION...")
        
        local_trans = self.get_all_local_transactions()
        print(f"📋 Local có {len(local_trans)} transaction pending")
        
        for trans in local_trans:
            if self.push_transaction_to_render(trans):
                print(f"  ✅ Push transaction {trans['code']}")
            time.sleep(0.2)
    
    def sync_user_balance(self, user_id):
        """Đồng bộ số dư user cụ thể từ Render về"""
        return self.pull_user_from_render(user_id)
    
    def run_daemon(self):
        """Chạy daemon tự động"""
        print("="*70)
        print("🚀 DAEMON ĐỒNG BỘ 2 CHIỀU - 10 GIÂY/LẦN")
        print("="*70)
        
        counter = 0
        while self.running:
            try:
                counter += 1
                print(f"\n🔄 Lần {counter} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Đồng bộ user
                self.sync_all_users()
                
                # Đồng bộ transaction
                self.sync_transactions()
                
                # Force sync user chính
                self.sync_user_balance(5180190297)
                
                time.sleep(10)  # 10 giây
                
            except KeyboardInterrupt:
                print("\n👋 Đã dừng daemon")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Lỗi daemon: {e}")
                time.sleep(5)
    
    def stop(self):
        self.running = False

if __name__ == "__main__":
    daemon = UserSyncDaemon()
    
    print("="*70)
    print("🔄 CÔNG CỤ ĐỒNG BỘ 2 CHIỀU")
    print("="*70)
    print("1. Đồng bộ user một lần")
    print("2. Đồng bộ transaction một lần")
    print("3. Đồng bộ cả user + transaction")
    print("4. Chạy daemon (tự động 10 giây)")
    print("5. Đồng bộ user cụ thể")
    print("6. Thoát")
    print("="*70)
    
    choice = input("Chọn (1-6): ").strip()
    
    if choice == "1":
        daemon.sync_all_users()
    elif choice == "2":
        daemon.sync_transactions()
    elif choice == "3":
        daemon.sync_all_users()
        daemon.sync_transactions()
    elif choice == "4":
        daemon.run_daemon()
    elif choice == "5":
        uid = int(input("Nhập user_id: "))
        daemon.sync_user_balance(uid)
    else:
        print("👋 Tạm biệt!")


