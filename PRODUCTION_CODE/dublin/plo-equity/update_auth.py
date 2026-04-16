import sys

# Read current app.py
with open('/opt/plo-equity/app.py', 'r') as f:
    content = f.read()

# Add auth_config import after Flask imports
import_section = """from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
import bcrypt
from functools import wraps"""

new_import_section = """from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
import bcrypt
from functools import wraps
from auth_config import require_auth, init_auth_config, AUTH_MODE"""

content = content.replace(import_section, new_import_section)

# Replace old login_required decorator
old_decorator = """def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function"""

# Comment out old decorator
new_decorator = """# Old login_required replaced by auth_config.require_auth
# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if 'username' not in session:
#             return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     return decorated_function"""

content = content.replace(old_decorator, new_decorator)

# Add auth init after app creation
app_creation = """app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)"""

new_app_creation = """app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)

# Initialize auth configuration
init_auth_config()"""

content = content.replace(app_creation, new_app_creation)

# Write updated content
with open('/opt/plo-equity/app.py', 'w') as f:
    f.write(content)

print("✅ Auth system updated")
print(f"✅ Mode: {AUTH_MODE if 'AUTH_MODE' in dir() else 'will use dev_bypass'}")
