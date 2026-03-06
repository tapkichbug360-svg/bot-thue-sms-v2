import sqlite3
import requests
import time
import os
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

def get_local_pending():
    """Lấy danh sách pending từ database local"""
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
        print(f"❌ Lỗi đọc database: {e}")
        return []

def sync_bidirectional():
    """Đồng bộ 2 chiều với Render"""
    try:
        local_pending = get_local_pending()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Local có {len(local_pending)} giao dịch pending")
        
        response = requests.post(
            f"{RENDER_URL}/api/sync-bidirectional",
            json={'local_transactions': local_pending},
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ Đồng bộ từ local lên Render: {result['synced_from_local']} giao dịch")
            print(f"📥 Render có {result['render_pending_count']} pending")
            
            sync_to_local = result.get('sync_to_local', [])
            if sync_to_local:
                print(f"📥 Cần đồng bộ {len(sync_to_local)} giao dịch từ Render về local")
                
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                synced = 0
                for trans in sync_to_local:
                    cursor.execute("SELECT id FROM users WHERE user_id = ?", (trans['user_id'],))
                    user = cursor.fetchone()
                    
                    if not user:
                        cursor.execute("""
                            INSERT INTO users (user_id, username, balance, created_at, last_active)
                            VALUES (?, ?, ?, ?, ?)
                        """, (trans['user_id'], f"user_{trans['user_id']}", 0, datetime.now(), datetime.now()))
                        user_id = cursor.lastrowid
                    else:
                        user_id = user[0]
                    
                    cursor.execute("""
                        INSERT INTO transactions 
                        (user_id, amount, type, status, transaction_code, description, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, trans['amount'], 'deposit', trans['status'], trans['code'],
                          f"Synced from Render: {trans['code']}", datetime.now()))
                    synced += 1
                    print(f"  ✅ Đã thêm {trans['code']} - {trans['amount']}đ - {trans['status']}")
                
                conn.commit()
                conn.close()
                print(f"✅ Đã đồng bộ {synced} giao dịch từ Render về local")
        else:
            print(f"❌ Lỗi HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Lỗi đồng bộ: {e}")

def force_sync_user(user_id):
    """Force đồng bộ tất cả giao dịch của một user"""
    try:
        response = requests.post(
            f"{RENDER_URL}/api/force-sync-user",
            json={'user_id': user_id},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ User {data['user_id']} - {data['username']}")
            print(f"💰 Balance: {data['balance']:,}đ")
            print(f"📊 Transactions: {len(data['transactions'])}")
            return data
        else:
            print(f"❌ Lỗi: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return None

if __name__ == "__main__":
    print("="*60)
    print("🔄 AUTO SYNC 2 CHIỀU LOCAL ↔ RENDER")
    print("⏱️  Chạy mỗi 10 giây")
    print("="*60)
    
    counter = 0
    while True:
        counter += 1
        print(f"\n🔄 Lần {counter} - {datetime.now().strftime('%H:%M:%S')}")
        sync_bidirectional()
        
        if counter % 6 == 0:
            print("\n📊 Kiểm tra user 5180190297:")
            force_sync_user(5180190297)
        
        time.sleep(10)