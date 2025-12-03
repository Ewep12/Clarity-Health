import sqlite3
conn = sqlite3.connect("instance/clarity_health.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE user ADD COLUMN telegram_chat_id TEXT;")
    print("telegram_chat_id criada.")
except Exception as e:
    print("telegram_chat_id:", e)

try:
    cur.execute("ALTER TABLE user ADD COLUMN trusted_telegram_id TEXT;")
    print("trusted_telegram_id criada.")
except Exception as e:
    print("trusted_telegram_id:", e)

conn.commit()
conn.close()
print("Pronto.")
