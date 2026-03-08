import sqlite3

print('📋 CÁC GIAO DỊCH PENDING:')
print('='*40)

conn = sqlite3.connect('database\\bot.db')
cursor = conn.cursor()

cursor.execute("SELECT transaction_code, amount, status FROM transactions WHERE status = 'pending'")
pending = cursor.fetchall()

if pending:
    for row in pending:
        print(f'  {row[0]}: {row[1]:,}đ - {row[2]}')
else:
    print('  ✅ Không có giao dịch pending nào!')

conn.close()
