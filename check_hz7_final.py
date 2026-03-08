import sqlite3

print('🔍 KIỂM TRA GIAO DỊCH HZ7MB1SX:')
print('='*40)

conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM transactions WHERE transaction_code = 'HZ7MB1SX'")
row = cursor.fetchone()

if row:
    print('✅ TÌM THẤY GIAO DỊCH:')
    print(f'  ID: {row[0]}')
    print(f'  User ID: {row[1]}')
    print(f'  Số tiền: {row[2]:,}đ')
    print(f'  Trạng thái: {row[4]}')
    print(f'  Mã GD: {row[6]}')
else:
    print('❌ KHÔNG TÌM THẤY giao dịch HZ7MB1SX trong database')

conn.close()
