import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from quetie.web.auth import SecurityManager

res = SecurityManager.authenticate_admin('admin', 'Qv7$9nLw2pR#sT1u8KmZ4gY!')
print(res)
