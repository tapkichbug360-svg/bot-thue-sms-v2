import sqlite3
from datetime import datetime

print('💰 ĐANG CẬP NHẬT SỐ DƯ...')
print('='*40)

# Kết nối database
conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

# Kiểm tra số dư hiện tại
cursor.execute('SELECT balance FROM users WHERE user_id = 5180190297')
old_balance = cursor.fetchone()[0]
print(f'📊 Số dư cũ: {old_balance:,}đ')

# Cập nhật số dư lên 91,000đ
cursor.execute('UPDATE users SET balance = 91000 WHERE user_id = 5180190297')

# Cập nhật trạng thái giao dịch LIL6E5XP thành success
cursor.execute("""
    UPDATE transactions 
    SET status = 'success', updated_at = ? 
    WHERE transaction_code = 'LIL6E5XP'
""", (datetime.now(),))

# Lưu thay đổi
conn.commit()

# Kiểm tra số dư mới
cursor.execute('SELECT balance FROM users WHERE user_id = 5180190297')
new_balance = cursor.fetchone()[0]
print(f'✅ ĐÃ CẬP NHẬT! Số dư mới: {new_balance:,}đ')

# Kiểm tra trạng thái giao dịch
cursor.execute("SELECT status FROM transactions WHERE transaction_code = 'LIL6E5XP'")
status = cursor.fetchone()[0]
print(f'📊 Trạng thái giao dịch LIL6E5XP: {status}')

# Đếm số giao dịch success
cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'success'")
success_count = cursor.fetchone()[0]
print(f'✅ Tổng số giao dịch success: {success_count}')

conn.close()


