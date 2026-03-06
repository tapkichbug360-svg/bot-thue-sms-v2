import sqlite3

print("📋 DANH SÁCH GIAO DỊCH PENDING")
print("="*50)

conn = sqlite3.connect('database/bot.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT t.transaction_code, t.amount, u.user_id, u.username, t.created_at
    FROM transactions t
    JOIN users u ON t.user_id = u.id
    WHERE t.status = 'pending'
    ORDER BY t.created_at DESC
""")

pending = cursor.fetchall()

if pending:
    for code, amount, uid, uname, created in pending:
        print(f"  {code}: {amount:,}đ - user {uid} (@{uname}) - {created}")
    print(f"\n✅ Tổng số: {len(pending)} giao dịch pending")
else:
    print("  ✅ Không có giao dịch pending nào!")

conn.close()