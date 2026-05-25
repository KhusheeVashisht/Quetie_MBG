#!/usr/bin/env python3
import sys
import sqlite3
from datetime import datetime

try:
    import bcrypt
except Exception:
    print('Missing dependency: bcrypt. Install with `pip install bcrypt`')
    raise

DB_PATH = 'quetie.db'

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    if len(sys.argv) < 3:
        print('Usage: set_admin_password.py USERNAME PASSWORD')
        sys.exit(2)
    username = sys.argv[1]
    password = sys.argv[2]
    pw_hash = hash_pw(password)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('SELECT id FROM admins WHERE username = ?', (username,))
    row = cur.fetchone()
    now = datetime.utcnow().isoformat()
    if row:
        cur.execute('UPDATE admins SET password_hash = ?, updated_at = ? WHERE id = ?', (pw_hash, now, row[0]))
        conn.commit()
        print(f'Updated password for existing admin: {username}')
    else:
        cur.execute(
            'INSERT INTO admins (username, password_hash, email, is_active, is_super_admin, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
            (username, pw_hash, f'{username}@local', 1, 1, now, now),
        )
        conn.commit()
        print(f'Created admin user: {username}')

    conn.close()

if __name__ == '__main__':
    main()
