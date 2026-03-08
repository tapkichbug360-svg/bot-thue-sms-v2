import sqlite3

print('🔍 KIỂM TRA GIAO DỊCH 3SG2WAE7')
print('='*40)

conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM transactions WHERE transaction_code = '3SG2WAE7'")
row = cursor.fetchone()

if row:
    print('✅ TÌM THẤY GIAO DỊCH:')
    print(f'  ID: {row[0]}')
    print(f'  User ID: {row[1]}')
    print(f'  Số tiền: {row[2]:,}đ')
    print(f'  Loại: {row[3]}')
    print(f'  Trạng thái: {row[4]}')
    print(f'  Mã GD: {row[6]}')
    print(f'  Nội dung: {row[7]}')
else:
    print('❌ KHÔNG TÌM THẤY giao dịch 3SG2WAE7 trong database')

conn.close()
