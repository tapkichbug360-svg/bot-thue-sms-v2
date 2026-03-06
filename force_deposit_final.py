import sqlite3
from datetime import datetime

print('💰 ĐANG CỘNG TIỀN...')
print('='*40)

# Kết nối database
conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

# Kiểm tra giao dịch hiện tại
cursor.execute("SELECT status FROM transactions WHERE transaction_code = 'UNOT6DOB'")
old_status = cursor.fetchone()
if old_status:
    print(f'📊 Trạng thái cũ: {old_status[0]}')
else:
    print('⚠️ Không tìm thấy giao dịch UNOT6DOB')

# Cập nhật giao dịch thành success
cursor.execute("""
    UPDATE transactions 
    SET status = ?, updated_at = ? 
    WHERE transaction_code = ?
""", ('success', datetime.now(), 'UNOT6DOB'))

# Cộng tiền cho user
cursor.execute("UPDATE users SET balance = balance + 20000 WHERE user_id = 5180190297")

# Lưu thay đổi
conn.commit()

# Kiểm tra số dư mới
cursor.execute("SELECT balance FROM users WHERE user_id = 5180190297")
new_balance = cursor.fetchone()[0]
print(f'✅ ĐÃ CỘNG 20,000đ THÀNH CÔNG!')
print(f'💰 Số dư cũ: 51,000đ → Số dư mới: {new_balance:,}đ')

# Kiểm tra trạng thái giao dịch mới
cursor.execute("SELECT status FROM transactions WHERE transaction_code = 'UNOT6DOB'")
new_status = cursor.fetchone()[0]
print(f'📊 Trạng thái mới: {new_status}')

# Đóng kết nối
conn.close()
