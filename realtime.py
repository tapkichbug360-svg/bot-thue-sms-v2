import sqlite3
import requests
import time
import os
from datetime import datetime

RENDER_URL = "https://bot-thue-sms-v2.onrender.com"

def get_all_users():
    """Láº¥y danh sÃ¡ch táº¥t cáº£ user tá»« local"""
    try:
        db_path = os.path.join('database', 'bot.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return users
    except Exception as e:
        print(f"âŒ Lá»—i láº¥y danh sÃ¡ch user: {e}")
        return []

def sync_all_users():
    """Äá»“ng bá»™ táº¥t cáº£ user vá»›i Render"""
    users = get_all_users()
    
    if not users:
        print("âš ï¸ KhÃ´ng cÃ³ user nÃ o Ä‘á»ƒ Ä‘á»“ng bá»™")
        return
    
    print(f"ðŸ”„ Äá»“ng bá»™ {len(users)} user...")
    
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
                
                # Cáº­p nháº­t local
                db_path = os.path.join('database', 'bot.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Láº¥y sá»‘ dÆ° cÅ©
                cursor.execute('SELECT balance FROM users WHERE user_id = %s', (user_id,))
                old = cursor.fetchone()
                old_balance = old[0] if old else 0
                
                # Cáº­p nháº­t sá»‘ dÆ° má»›i
                cursor.execute('UPDATE users SET balance = %s WHERE user_id = %s', (render_balance, user_id))
                
                # Cáº­p nháº­t tráº¡ng thÃ¡i giao dá»‹ch
                for trans in data['transactions']:
                    cursor.execute("""
                        UPDATE transactions 
                        SET status = %s, updated_at = %s 
                        WHERE transaction_code = %s
                    """, (trans['status'], datetime.now(), trans['code']))
                
                conn.commit()
                conn.close()
                
                if old_balance != render_balance:
                    print(f"  âœ… User {user_id}: {old_balance}Ä‘ â†’ {render_balance}Ä‘")
            else:
                print(f"  âŒ User {user_id}: Lá»—i {response.status_code}")
                
        except Exception as e:
            print(f"  âŒ User {user_id}: {e}")
        
        time.sleep(0.5)  # TrÃ¡nh spam API

if __name__ == "__main__":
    print("="*60)
    print("ðŸ”„ Äá»’NG Bá»˜ Táº¤T Cáº¢ USER LOCAL â†” RENDER")
    print("="*60)
    
    sync_all_users()
