import sqlite3

# conn = sqlite3.connect("data/memory.db")

# cursor = conn.cursor()

# try:
#     cursor.execute("ALTER TABLE conversations ADD COLUMN conversation_id TEXT;")
#     print("✅ Column added successfully")
# except Exception as e:
#     print("⚠️ Column may already exist:", e)

# # Backfill old data
# cursor.execute("UPDATE conversations SET conversation_id = 'legacy_' || id;")
# print("✅ Old data updated")

# conn.commit()
# conn.close()

# print("🎉 Migration completed")

conn = sqlite3.connect("data/memory.db")
rows = conn.execute("PRAGMA table_info(conversations)").fetchall()

for r in rows:
    print(r)

conn.close()