import sqlite3

conn = sqlite3.connect('C:\\bot_thue_sms_24h\\database\\bot.db')
cursor = conn.cursor()

# Kiểm tra giao dịch
cursor.execute("SELECT status FROM transactions WHERE transaction_code = 'L7S5ZBIJ'")
status = cursor.fetchone()
if status:
    print(f'📊 Trạng thái giao dịch: {status[0]}')
else:
    print('❌ Không tìm thấy giao dịch')

# Kiểm tra số dư
cursor.execute("SELECT balance FROM users WHERE user_id = 5180190297")
balance = cursor.fetchone()
if balance:
    print(f'💰 Số dư hiện tại: {balance[0]:,}đ')
else:
    print('❌ Không tìm thấy user')

conn.close()
