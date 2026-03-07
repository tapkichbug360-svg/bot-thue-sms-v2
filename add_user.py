import sqlite3
from datetime import datetime

print('➕ THÊM USER 7452863721:')
print('='*40)

conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM users WHERE user_id = 7452863721")
row = cursor.fetchone()

if row:
    print('✅ User đã tồn tại, bỏ qua')
    print(f'  ID: {row[0]}')
    print(f'  User ID: {row[1]}')
    print(f'  Username: {row[2]}')
    print(f'  Balance: {row[3]:,}đ')
else:
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at, last_active)
        VALUES (%s, %s, %s, %s, %s)
    """, (7452863721, 'unknown_user', 0, datetime.now(), datetime.now()))
    conn.commit()
    print('✅ Đã thêm user 7452863721 vào database')

conn.close()

