import sqlite3, bcrypt
conn=sqlite3.connect('quetie.db')
cur=conn.cursor()
cur.execute("SELECT password_hash FROM admins WHERE username='admin'")
hash=cur.fetchone()[0]
conn.close()
print('hash=', hash)
print('check=', bcrypt.checkpw('admin123'.encode(), hash.encode()))
