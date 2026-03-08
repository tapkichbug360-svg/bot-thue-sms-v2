import sqlite3
import os

db_path = os.path.join('C:\\', 'bot_thue_sms_24h', 'database', 'bot.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('🔍 KIỂM TRA GIAO DỊCH L7S5ZBIJ')
print('='*40)

# Kiểm tra giao dịch
cursor.execute("SELECT * FROM transactions WHERE transaction_code = 'L7S5ZBIJ'")
transaction = cursor.fetchone()

if transaction:
    print('✅ TÌM THẤY GIAO DỊCH:')
    print(f'  ID: {transaction[0]}')
    print(f'  User ID: {transaction[1]}')
    print(f'  Số tiền: {transaction[2]:,}đ')
    print(f'  Loại: {transaction[3]}')
    print(f'  Trạng thái: {transaction[4]}')
    print(f'  Mã GD: {transaction[6]}')
    print(f'  Nội dung: {transaction[7]}')
else:
    print('❌ KHÔNG TÌM THẤY giao dịch L7S5ZBIJ')

# Kiểm tra số dư user
cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = 5180190297")
user = cursor.fetchone()
if user:
    print(f'\n💰 SỐ DƯ USER {user[0]}:')
    print(f'  Username: {user[1]}')
    print(f'  Số dư: {user[2]:,}đ')
else:
    print('\n❌ Không tìm thấy user')

conn.close()
