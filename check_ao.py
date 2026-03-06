import sqlite3

print('🔍 KIỂM TRA GIAO DỊCH ẢO:')
print('='*40)

conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

# Đếm giao dịch pending
cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
pending = cursor.fetchone()[0]

# Đếm giao dịch success
cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'success'")
success = cursor.fetchone()[0]

print(f'📊 Giao dịch pending: {pending}')
print(f'✅ Giao dịch success: {success}')

# Kiểm tra số dư
cursor.execute("SELECT balance FROM users WHERE user_id = 5180190297")
balance = cursor.fetchone()[0]
print(f'💰 Số dư ảo: {balance:,}đ')

conn.close()
