import httpx
import os

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8000')
ADMIN_USER = os.getenv('E2E_ADMIN_USER', 'admin')
ADMIN_PASS = os.getenv('E2E_ADMIN_PASS', 'admin123')

print('E2E check starting...')
with httpx.Client(base_url=BASE, timeout=10.0) as client:
    # login
    r = client.post('/api/auth/login', json={'username': ADMIN_USER, 'password': ADMIN_PASS})
    print('login status', r.status_code)
    if r.status_code != 200:
        print('Login failed:', r.text)
        raise SystemExit(1)
    token = r.json().get('token')
    print('token len', len(token or ''))

    # create session -> sets cookies
    r2 = client.post('/api/auth/session', headers={'Authorization': f'Bearer {token}'})
    print('create session status', r2.status_code)
    print('cookies after session:', client.cookies)
    csrf = client.cookies.get('quetie_csrf')
    print('csrf cookie present?', bool(csrf))
    if not csrf:
        raise SystemExit('No csrf cookie')

    # attempt to create a temp admin using cookie+csrf header
    payload = {'username': 'e2e_test_user', 'password': 'testpass123', 'email': 'e2e@example.com'}
    headers = {'X-CSRF-Token': csrf}
    r3 = client.post('/api/admins', json=payload, headers=headers)
    print('/api/admins create status', r3.status_code, r3.text[:400])
    if r3.status_code not in (200,201):
        raise SystemExit('Create admin failed')

    # cleanup: remove created admin if present
    print('E2E check passed')

