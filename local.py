import sqlite3
import requests
import time
import os
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

def get_local_pending():
    """Láº¥y danh sÃ¡ch pending tá»« database local"""
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
        print(f"âŒ Lá»—i Ä‘á»c database: {e}")
        return []

def sync_bidirectional():
    """Äá»“ng bá»™ 2 chiá»u vá»›i Render"""
    try:
        local_pending = get_local_pending()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ðŸ“¤ Local cÃ³ {len(local_pending)} giao dá»‹ch pending")
        
        # Chá»‰ gá»­i náº¿u cÃ³ giao dá»‹ch
        if not local_pending:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] âœ… KhÃ´ng cÃ³ giao dá»‹ch cáº§n Ä‘á»“ng bá»™")
            return
        
        response = requests.post(
            f"{RENDER_URL}/api/sync-bidirectional",
            json={'local_transactions': local_pending},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"âœ… Äá»“ng bá»™ tá»« local lÃªn Render: {result['synced_from_local']} giao dá»‹ch")
            print(f"ðŸ“¥ Render cÃ³ {result['render_pending_count']} pending")
            
            # Xá»­ lÃ½ Ä‘á»“ng bá»™ vá» local náº¿u cÃ³
            sync_to_local = result.get('sync_to_local', [])
            if sync_to_local:
                print(f"ðŸ“¥ Render gá»­i vá» {len(sync_to_local)} giao dá»‹ch")
                
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                for trans in sync_to_local:
                    # Kiá»ƒm tra user Ä‘Ã£ cÃ³ chÆ°a
                    cursor.execute("SELECT id FROM users WHERE user_id = %s", (trans['user_id'],))
                    user = cursor.fetchone()
                    
                    if not user:
                        # Táº¡o user má»›i
                        cursor.execute("""
                            INSERT INTO users (user_id, username, balance, created_at, last_active)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (trans['user_id'], f"user_{trans['user_id']}", 0, datetime.now(), datetime.now()))
                        user_id = cursor.lastrowid
                    else:
                        user_id = user[0]
                    
                    # Kiá»ƒm tra giao dá»‹ch Ä‘Ã£ cÃ³ chÆ°a
                    cursor.execute("SELECT id FROM transactions WHERE transaction_code = %s", (trans['code'],))
                    existing = cursor.fetchone()
                    
                    if not existing:
                        cursor.execute("""
                            INSERT INTO transactions 
                            (user_id, amount, type, status, transaction_code, description, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (user_id, trans['amount'], 'deposit', trans['status'], trans['code'],
                              f"Synced from Render: {trans['code']}", datetime.now()))
                        print(f"  âœ… ÄÃ£ thÃªm {trans['code']} - {trans['amount']}Ä‘ - {trans['status']}")
                
                conn.commit()
                conn.close()
        else:
            print(f"âŒ Lá»—i HTTP {response.status_code}")
            try:
                error_detail = response.json()
                print(f"ðŸ“ Chi tiáº¿t: {error_detail}")
            except:
                print(f"ðŸ“ Response: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"âŒ Timeout - Server Render quÃ¡ táº£i")
    except requests.exceptions.ConnectionError:
        print(f"âŒ KhÃ´ng thá»ƒ káº¿t ná»‘i Ä‘áº¿n Render")
    except Exception as e:
        print(f"âŒ Lá»—i Ä‘á»“ng bá»™: {e}")

def force_sync_user(user_id):
    """Force Ä‘á»“ng bá»™ táº¥t cáº£ giao dá»‹ch cá»§a má»™t user"""
    try:
        response = requests.post(
            f"{RENDER_URL}/api/force-sync-user",
            json={'user_id': user_id},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"âœ… User {data['user_id']} - {data['username']}")
            print(f"ðŸ’° Balance: {data['balance']:,}Ä‘")
            print(f"ðŸ“Š Transactions: {len(data['transactions'])}")
            return data
        else:
            print(f"âŒ Lá»—i: {response.status_code}")
            return None
    except Exception as e:
        print(f"âŒ Lá»—i: {e}")
        return None

if __name__ == "__main__":
    print("="*60)
    print("ðŸ”„ AUTO SYNC 2 CHIá»€U LOCAL â†” RENDER (FIXED VERSION)")
    print("â±ï¸  Cháº¡y má»—i 10 giÃ¢y")
    print("="*60)
    
    counter = 0
    while True:
        counter += 1
        print(f"\nðŸ”„ Láº§n {counter} - {datetime.now().strftime('%H:%M:%S')}")
        sync_bidirectional()
        
        # Má»—i 6 láº§n (60 giÃ¢y) kiá»ƒm tra user cá»¥ thá»ƒ
        if counter % 6 == 0:
            print("\nðŸ“Š Kiá»ƒm tra user 5180190297:")
            force_sync_user(5180190297)
        
        time.sleep(10)


