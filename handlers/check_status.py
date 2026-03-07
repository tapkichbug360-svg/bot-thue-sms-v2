import sqlite3
from bot import app

print("🔍 KIỂM TRA TRẠNG THÁI HỆ THỐNG")
print("="*50)

conn = sqlite3.connect('database/bot.db')
cursor = conn.cursor()

# Kiểm tra users
cursor.execute("SELECT COUNT(*) FROM users")
total_users = cursor.fetchone()[0]
print(f"👥 Tổng users: {total_users}")

# Kiểm tra transactions
cursor.execute("SELECT COUNT(*) FROM transactions")
total_trans = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
pending = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'success'")
success = cursor.fetchone()[0]
print(f"📊 Transactions: {total_trans} (pending: {pending}, success: {success})")

# Kiểm tra số dư user cụ thể
user_id = 5180190297
cursor.execute("SELECT username, balance FROM users WHERE user_id = %s", (user_id,))
user = cursor.fetchone()
if user:
    print(f"💰 User {user_id} (@{user[0]}): {user[1]:,}đ")
else:
    print(f"❌ Không tìm thấy user {user_id}")

conn.close()
