import sqlite3, json
conn=sqlite3.connect('quetie.db')
cur=conn.cursor()
cur.execute("SELECT id, username, password_hash FROM admins WHERE username = 'admin'")
row=cur.fetchone()
print(json.dumps(row, default=str))
conn.close()
