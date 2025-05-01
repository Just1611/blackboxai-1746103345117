from flask import Flask, render_template, redirect, request, session, jsonify, Response
from flask_cors import CORS
from flask_sock import Sock
import requests
import json
import os
import sys
import jwt
import bcrypt
import time
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

# Import Steam authentication
from steam_auth import init_steam_auth, auth_attempts

# Initialize WebSocket
sock = Sock()

# Role-based middleware
def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('authenticated'):
                return redirect('/login.html')
            
            user_role = session.get('role', 'user')
            if user_role not in roles:
                return jsonify({'error': 'Unauthorized access'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Admin middleware
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or session.get('role') != 'admin':
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# Staff middleware
def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or session.get('role') not in ['admin', 'staff']:
            return redirect('/login.html')
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('/login.html')
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)
sock.init_app(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# WebSocket connections store
ws_connections = set()

@sock.route('/ws/admin/stats')
@admin_required
def admin_stats_ws(ws):
    """WebSocket endpoint for real-time admin stats"""
    try:
        # Add connection to set
        ws_connections.add(ws)
        
        while True:
            try:
                # Get current stats
                current_time = datetime.utcnow().replace(tzinfo=None)
                
                # Get active users (users who logged in within last 24 hours)
                active_users = len([
                    user for user in USERS_DB.values()
                    if user.get('loginHistory') and
                    any(
                        (current_time - datetime.fromisoformat(login['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
                        for login in user['loginHistory']
                    )
                ])

                # Calculate daily trades
                daily_trades = sum(
                    1 for user in USERS_DB.values()
                    for trade in user.get('trades', [])
                    if (current_time - datetime.fromisoformat(trade['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
                )

                # Calculate cases opened today
                cases_opened = sum(
                    1 for user in USERS_DB.values()
                    for case in user.get('cases_opened', [])
                    if (current_time - datetime.fromisoformat(case['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
                )

                # Calculate net profit from trades and cases
                net_profit = sum(
                    sum(trade.get('value', 0) for trade in user.get('trades', [])
                        if (current_time - datetime.fromisoformat(trade['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400)
                    for user in USERS_DB.values()
                )

                # Only try to fetch Steam stats if we're not in demo mode
                if not DEMO_MODE and STEAM_API_KEY and STEAM_API_KEY != 'demo_mode':
                    try:
                        # Get Steam market stats
                        market_stats = requests.get(
                            f'{STEAM_API_URL}/IEconService/GetTradeHistory/v1/',
                            params={'key': STEAM_API_KEY, 'max_trades': 500, 'start_after_time': int((current_time - timedelta(days=1)).timestamp())},
                            timeout=10
                        )
                        
                        if market_stats.status_code == 200:
                            market_data = market_stats.json()
                            if 'response' in market_data:
                                daily_trades = len(market_data['response'].get('trades', []))
                                net_profit = sum(
                                    float(trade.get('asset_value', 0))
                                    for trade in market_data['response'].get('trades', [])
                                )

                        # Get online players count
                        players_stats = requests.get(
                            f'{STEAM_API_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/',
                            params={'appid': 730},  # CS2 App ID
                            timeout=10
                        )
                        
                        if players_stats.status_code == 200:
                            players_data = players_stats.json()
                            if 'response' in players_data:
                                active_users = players_data['response'].get('player_count', active_users)

                    except Exception as e:
                        app.logger.warning(f"Steam API unavailable, using local stats: {str(e)}")

                # Send stats update
                ws.send(json.dumps({
                    'daily_trades': daily_trades,
                    'active_users': active_users,
                    'cases_opened': cases_opened,
                    'net_profit': round(net_profit, 2)
                }))
                
                # Wait for 5 seconds before next update
                time.sleep(5)
                
            except Exception as e:
                app.logger.error(f"Error updating stats: {str(e)}")
                # Continue the loop even if there's an error
                time.sleep(5)
                continue
            
    except Exception as e:
        app.logger.error(f"WebSocket error: {str(e)}")
    finally:
        # Remove connection from set when done
        ws_connections.remove(ws)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure Steam API
STEAM_API_KEY = os.getenv('STEAM_API_KEY', 'demo_mode')
STEAM_API_URL = 'https://api.steampowered.com'
DEMO_MODE = STEAM_API_KEY == 'demo_mode'

# Initialize Steam authentication
init_steam_auth(app, STEAM_API_KEY, USERS_DB, generate_jwt_token)
if DEMO_MODE:
    app.logger.warning("Running in DEMO MODE - Steam API features will be simulated")
    
    # Demo user data
    DEMO_USER = {
        'steamid': '76561198123456789',
        'personaname': 'Demo User',
        'avatarfull': 'https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg',
        'profileurl': 'https://steamcommunity.com/profiles/76561198123456789'
    }
    
    # Demo inventory data
    DEMO_INVENTORY = [
        {
            'id': '1234567890',
            'name': 'AWP | Dragon Lore (Factory New)',
            'type': 'Sniper Rifle',
            'wear': '0.01',
            'price': '10000.00',
            'imageUrl': 'https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpot621FAR17P7NdTRH-t26q4SZlvD7PYTQgXtu5Mx2gv3--Y3nj1H6qBFvMWHyIo7Adw9raF6GrlK5xLrmh8PptZrJnyNn7HYj7WGdwULz5Q_xUw/360fx360f'
        },
        {
            'id': '0987654321',
            'name': 'M4A4 | Howl (Factory New)',
            'type': 'Rifle',
            'wear': '0.02',
            'price': '8000.00',
            'imageUrl': 'https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpou-6kejhjxszFJTwW09-vloWZh-DLPr7Vn35c18lwmO7Eu9TwjVbs8xVrMWvzJ4fGclRqYw2C-1e9w-u91JXvuJvBzXZnuCkj5imPlUGpwUYb8Zk_Qqs/360fx360f'
        }
    ]

# Session and JWT configuration
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
JWT_SECRET = os.getenv('JWT_SECRET', os.urandom(24))
JWT_EXPIRATION = 3600  # 1 hour

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock admin credentials (in production, use a database)
ADMIN_CREDENTIALS = {
    'admin': {
        'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()),
        'role': 'admin',
        '2fa_secret': 'JBSWY3DPEHPK3PXP'  # Example 2FA secret
    },
    'staff': {
        'password': bcrypt.hashpw('staff123'.encode('utf-8'), bcrypt.gensalt()),
        'role': 'staff',
        '2fa_secret': 'KRSXG5CTMVRXEZLU'  # Example 2FA secret
    }
}

# Initialize test data
USERS_DB = {
    'user1': {
        'username': 'trader123',
        'loginHistory': [
            {'date': datetime.utcnow().isoformat()},
            {'date': (datetime.utcnow() - timedelta(hours=2)).isoformat()}
        ],
        'trades': [
            {
                'date': datetime.utcnow().isoformat(),
                'value': 150.50,
                'type': 'sell'
            },
            {
                'date': (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                'value': 75.25,
                'type': 'buy'
            }
        ],
        'cases_opened': [
            {
                'date': datetime.utcnow().isoformat(),
                'case_id': 'case1',
                'result': 'rare_skin'
            },
            {
                'date': (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                'case_id': 'case2',
                'result': 'common_skin'
            }
        ]
    },
    'user2': {
        'username': 'csgo_pro',
        'loginHistory': [
            {'date': datetime.utcnow().isoformat()},
            {'date': (datetime.utcnow() - timedelta(hours=1)).isoformat()}
        ],
        'trades': [
            {
                'date': datetime.utcnow().isoformat(),
                'value': 320.75,
                'type': 'sell'
            },
            {
                'date': (datetime.utcnow() - timedelta(minutes=45)).isoformat(),
                'value': 180.00,
                'type': 'buy'
            }
        ],
        'cases_opened': [
            {
                'date': datetime.utcnow().isoformat(),
                'case_id': 'case3',
                'result': 'legendary_skin'
            }
        ]
    }
}

# Mock database for failed login attempts
failed_login_attempts = {}

def generate_jwt_token(username, role):
    """Generate a JWT token for admin authentication"""
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_2fa_code(secret, code):
    """Verify 2FA code (mock implementation)"""
    # In production, use proper 2FA library like pyotp
    return code == '123456'  # Mock verification

def log_failed_attempt(username, ip):
    """Log failed login attempts"""
    current_time = time.time()
    if username not in failed_login_attempts:
        failed_login_attempts[username] = []
    
    # Remove attempts older than 1 hour
    failed_login_attempts[username] = [
        attempt for attempt in failed_login_attempts[username]
        if current_time - attempt['timestamp'] < 3600
    ]
    
    failed_login_attempts[username].append({
        'timestamp': current_time,
        'ip': ip
    })
    
    return len(failed_login_attempts[username])

# Admin routes
@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    if session.get('authenticated') and session.get('role') == 'admin':
        return redirect('/admin/dashboard')
    return app.send_static_file('admin/login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return app.send_static_file('admin/dashboard.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    twoFactorCode = data.get('twoFactorCode')
    
    if not username or not password or not twoFactorCode:
        return jsonify({'error': 'Missing credentials'}), 400
        
    # Check if account is locked
    attempts = failed_login_attempts.get(username, [])
    recent_attempts = [
        attempt for attempt in attempts
        if time.time() - attempt['timestamp'] < 3600
    ]
    if len(recent_attempts) >= 5:
        return jsonify({'error': 'Account locked. Try again later.'}), 403
    
    # Verify credentials
    user_data = ADMIN_CREDENTIALS.get(username)
    if not user_data:
        log_failed_attempt(username, request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401
        
    if not bcrypt.checkpw(password.encode('utf-8'), user_data['password']):
        log_failed_attempt(username, request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401
        
    # Verify 2FA
    if not verify_2fa_code(user_data['2fa_secret'], twoFactorCode):
        log_failed_attempt(username, request.remote_addr)
        return jsonify({'error': 'Invalid 2FA code'}), 401
    
    # Clear failed attempts on successful login
    failed_login_attempts.pop(username, None)
    
    # Set session data
    session['authenticated'] = True
    session['username'] = username
    session['role'] = user_data['role']
    
    # Generate JWT token
    token = generate_jwt_token(username, user_data['role'])
    
    return jsonify({
        'token': token,
        'admin': {
            'username': username,
            'role': user_data['role']
        }
    })

@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Get real-time admin dashboard statistics"""
    try:
        # Get active users (users who logged in within last 24 hours)
        current_time = datetime.utcnow().replace(tzinfo=None)
        active_users = len([
            user for user in USERS_DB.values()
            if user.get('loginHistory') and
            any(
                (current_time - datetime.fromisoformat(login['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
                for login in user['loginHistory']
            )
        ])

        # Calculate daily trades
        daily_trades = sum(
            1 for user in USERS_DB.values()
            for trade in user.get('trades', [])
            if (current_time - datetime.fromisoformat(trade['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
        )

        # Calculate cases opened today
        cases_opened = sum(
            1 for user in USERS_DB.values()
            for case in user.get('cases_opened', [])
            if (current_time - datetime.fromisoformat(case['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400
        )

        # Calculate net profit from trades and cases
        net_profit = sum(
            sum(trade.get('value', 0) for trade in user.get('trades', [])
                if (current_time - datetime.fromisoformat(trade['date'].replace('Z', '')).replace(tzinfo=None)).total_seconds() < 86400)
            for user in USERS_DB.values()
        )

        # Only try to fetch Steam stats if we're not in demo mode
        if not DEMO_MODE and STEAM_API_KEY and STEAM_API_KEY != 'demo_mode':
            try:
                # Get Steam market stats
                market_stats = requests.get(
                    f'{STEAM_API_URL}/IEconService/GetTradeHistory/v1/',
                    params={'key': STEAM_API_KEY, 'max_trades': 500, 'start_after_time': int((current_time - timedelta(days=1)).timestamp())},
                    timeout=10
                )
                
                if market_stats.status_code == 200:
                    market_data = market_stats.json()
                    if 'response' in market_data:
                        daily_trades = len(market_data['response'].get('trades', []))
                        net_profit = sum(
                            float(trade.get('asset_value', 0))
                            for trade in market_data['response'].get('trades', [])
                        )

                # Get online players count
                players_stats = requests.get(
                    f'{STEAM_API_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/',
                    params={'appid': 730},  # CS2 App ID
                    timeout=10
                )
                
                if players_stats.status_code == 200:
                    players_data = players_stats.json()
                    if 'response' in players_data:
                        active_users = players_data['response'].get('player_count', active_users)

            except Exception as e:
                app.logger.warning(f"Steam API unavailable, using local stats: {str(e)}")

        return jsonify({
            'daily_trades': daily_trades,
            'active_users': active_users,
            'cases_opened': cases_opened,
            'net_profit': round(net_profit, 2)
        })

    except Exception as e:
        app.logger.error(f"Error getting admin stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

# Case Management Routes
@app.route('/admin/cases')
@admin_required
def cases_page():
    return app.send_static_file('admin/cases.html')

# Mock database for cases
CASES_DB = {
    'case_1': {
        'id': 'case_1',
        'name': 'Cyber Dreams Case',
        'price': 2.49,
        'imageUrl': 'https://example.com/case1.jpg',
        'active': True,
        'items': [
            {
                'name': 'AWP | Neo-Noir',
                'rarity': 'covert',
                'dropRate': 0.64
            },
            {
                'name': 'M4A4 | Cyber Security',
                'rarity': 'classified',
                'dropRate': 3.2
            }
        ]
    }
}

@app.route('/api/admin/cases', methods=['GET'])
@admin_required
def get_cases():
    """Get all cases"""
    return jsonify(list(CASES_DB.values()))

@app.route('/api/admin/cases/<case_id>', methods=['GET'])
@admin_required
def get_case(case_id):
    """Get specific case"""
    case = CASES_DB.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    return jsonify(case)

@app.route('/api/admin/cases', methods=['POST'])
@admin_required
def create_case():
    """Create new case"""
    try:
        # Handle file upload
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
            
        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'No image selected'}), 400
            
        # In production, save image to cloud storage and get URL
        image_url = f'https://example.com/{image.filename}'
        
        # Get case data
        case_id = f'case_{len(CASES_DB) + 1}'
        case_data = {
            'id': case_id,
            'name': request.form.get('name'),
            'price': float(request.form.get('price')),
            'imageUrl': image_url,
            'active': True,
            'items': []
        }
        
        # Process items
        items_data = request.form.getlist('items[][name]')
        items_rarity = request.form.getlist('items[][rarity]')
        items_rate = request.form.getlist('items[][dropRate]')
        
        for i in range(len(items_data)):
            case_data['items'].append({
                'name': items_data[i],
                'rarity': items_rarity[i],
                'dropRate': float(items_rate[i])
            })
            
        # Validate total drop rate is 100%
        total_rate = sum(item['dropRate'] for item in case_data['items'])
        if not (99.9 <= total_rate <= 100.1):  # Allow small floating point variance
            return jsonify({'error': 'Total drop rate must equal 100%'}), 400
            
        # Save case
        CASES_DB[case_id] = case_data
        
        return jsonify(case_data), 201
        
    except Exception as e:
        app.logger.error(f'Error creating case: {str(e)}')
        return jsonify({'error': 'Failed to create case'}), 500

@app.route('/api/admin/cases/<case_id>', methods=['PUT'])
@admin_required
def update_case(case_id):
    """Update existing case"""
    if case_id not in CASES_DB:
        return jsonify({'error': 'Case not found'}), 404
        
    try:
        case = CASES_DB[case_id]
        
        # Update basic info
        case['name'] = request.form.get('name', case['name'])
        case['price'] = float(request.form.get('price', case['price']))
        
        # Update image if provided
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            # In production, save image to cloud storage and get URL
            case['imageUrl'] = f'https://example.com/{image.filename}'
            
        # Update items if provided
        if 'items[][name]' in request.form:
            case['items'] = []
            items_data = request.form.getlist('items[][name]')
            items_rarity = request.form.getlist('items[][rarity]')
            items_rate = request.form.getlist('items[][dropRate]')
            
            for i in range(len(items_data)):
                case['items'].append({
                    'name': items_data[i],
                    'rarity': items_rarity[i],
                    'dropRate': float(items_rate[i])
                })
                
            # Validate total drop rate
            total_rate = sum(item['dropRate'] for item in case['items'])
            if not (99.9 <= total_rate <= 100.1):
                return jsonify({'error': 'Total drop rate must equal 100%'}), 400
                
        return jsonify(case)
        
    except Exception as e:
        app.logger.error(f'Error updating case: {str(e)}')
        return jsonify({'error': 'Failed to update case'}), 500

@app.route('/api/admin/cases/<case_id>/toggle', methods=['POST'])
@admin_required
def toggle_case(case_id):
    """Toggle case active status"""
    if case_id not in CASES_DB:
        return jsonify({'error': 'Case not found'}), 404
        
    CASES_DB[case_id]['active'] = not CASES_DB[case_id]['active']
    return jsonify(CASES_DB[case_id])

@app.route('/api/admin/cases/<case_id>', methods=['DELETE'])
@admin_required
def delete_case(case_id):
    """Delete case"""
    if case_id not in CASES_DB:
        return jsonify({'error': 'Case not found'}), 404
        
    del CASES_DB[case_id]
    return '', 204

# Mock user database
USERS_DB = {
    '76561198123456789': {
        'steamId': '76561198123456789',
        'username': 'CyberTrader',
        'role': 'user',
        'status': 'active',
        'avatarUrl': 'https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg',
        'totalTrades': 157,
        'balance': 2489.50,
        'trades': [
            {
                'date': '2024-04-17T10:30:00Z',
                'type': 'deposit',
                'items': ['AWP | Dragon Lore (Factory New)'],
                'value': 10000.00
            },
            {
                'date': '2024-04-16T15:45:00Z',
                'type': 'withdraw',
                'items': ['M4A4 | Howl (Factory New)'],
                'value': 8000.00
            }
        ],
        'loginHistory': [
            {
                'date': '2024-04-17T10:00:00Z',
                'ip': '192.168.1.1',
                'location': 'New York, US'
            },
            {
                'date': '2024-04-16T14:30:00Z',
                'ip': '192.168.1.1',
                'location': 'New York, US'
            }
        ]
    }
}

# User Management Routes
@app.route('/admin/users')
@admin_required
def users_page():
    return app.send_static_file('admin/users.html')

@app.route('/api/admin/users')
@admin_required
def get_users():
    """Get all users"""
    return jsonify(list(USERS_DB.values()))

@app.route('/api/admin/users/<steam_id>')
@admin_required
def get_user(steam_id):
    """Get specific user"""
    user = USERS_DB.get(steam_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user)

@app.route('/api/admin/users/<steam_id>/trades')
@admin_required
def get_user_trades(steam_id):
    """Get user's trading history"""
    user = USERS_DB.get(steam_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.get('trades', []))

@app.route('/api/admin/users/<steam_id>/logins')
@admin_required
def get_user_logins(steam_id):
    """Get user's login history"""
    user = USERS_DB.get(steam_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.get('loginHistory', []))

@app.route('/api/admin/users/<steam_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(steam_id):
    """Toggle user's active status"""
    user = USERS_DB.get(steam_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    user['status'] = 'banned' if user['status'] == 'active' else 'active'
    
    # Log the action
    app.logger.info(f"Admin {session['username']} {'banned' if user['status'] == 'banned' else 'unbanned'} user {steam_id}")
    
    return jsonify(user)

@app.route('/api/admin/users/<steam_id>/role', methods=['PUT'])
@admin_required
def update_user_role(steam_id):
    """Update user's role"""
    user = USERS_DB.get(steam_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ['user', 'staff', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
        
    # Prevent self-demotion
    if steam_id == session.get('steam_id') and new_role != 'admin':
        return jsonify({'error': 'Cannot demote yourself'}), 403
        
    user['role'] = new_role
    
    # Log the action
    app.logger.info(f"Admin {session['username']} updated role for user {steam_id} to {new_role}")
    
    return jsonify(user)

@app.route('/api/admin/users/export', methods=['GET'])
@admin_required
def export_users():
    """Export user data as CSV"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Steam ID', 'Username', 'Role', 'Status', 'Total Trades', 'Balance'])
    
    # Write user data
    for user in USERS_DB.values():
        writer.writerow([
            user['steamId'],
            user['username'],
            user['role'],
            user['status'],
            user['totalTrades'],
            user['balance']
        ])
    
    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users.csv'}
    )

# Mock database for bots
BOTS_DB = {
    'bot_1': {
        'id': 'bot_1',
        'name': 'Trading Bot #1',
        'active': True,
        'totalTrades': 1247,
        'successRate': 99.8,
        'inventoryValue': 25789.50,
        'items': [
            {
                'name': 'AWP | Dragon Lore (Factory New)',
                'assetId': '123456789',
                'value': 10000.00
            },
            {
                'name': 'M4A4 | Howl (Factory New)',
                'assetId': '987654321',
                'value': 8000.00
            }
        ]
    }
}

# Bot Management Routes
@app.route('/admin/bots')
@admin_required
def bots_page():
    return app.send_static_file('admin/bots.html')

@app.route('/api/admin/bots')
@admin_required
def get_bots():
    """Get all bots and stats"""
    active_bots = sum(1 for bot in BOTS_DB.values() if bot['active'])
    total_items = sum(len(bot['items']) for bot in BOTS_DB.values())
    total_value = sum(
        sum(item['value'] for item in bot['items'])
        for bot in BOTS_DB.values()
    )
    
    return jsonify({
        'stats': {
            'activeBots': active_bots,
            'totalItems': total_items,
            'totalValue': total_value
        },
        'bots': list(BOTS_DB.values())
    })

@app.route('/api/admin/bots/<bot_id>')
@admin_required
def get_bot(bot_id):
    """Get specific bot"""
    bot = BOTS_DB.get(bot_id)
    if not bot:
        return jsonify({'error': 'Bot not found'}), 404
    return jsonify(bot)

@app.route('/api/admin/bots', methods=['POST'])
@admin_required
def create_bot():
    """Create new bot"""
    try:
        data = request.json
        
        # Generate new bot ID
        bot_id = f'bot_{len(BOTS_DB) + 1}'
        
        # Create bot
        bot = {
            'id': bot_id,
            'name': data['name'],
            'active': False,
            'totalTrades': 0,
            'successRate': 100.0,
            'inventoryValue': 0.00,
            'items': []
        }
        
        BOTS_DB[bot_id] = bot
        
        # Log the action
        app.logger.info(f"Admin {session['username']} created bot {bot_id}")
        
        return jsonify(bot), 201
        
    except Exception as e:
        app.logger.error(f'Error creating bot: {str(e)}')
        return jsonify({'error': 'Failed to create bot'}), 500

@app.route('/api/admin/bots/<bot_id>', methods=['PUT'])
@admin_required
def update_bot(bot_id):
    """Update bot"""
    if bot_id not in BOTS_DB:
        return jsonify({'error': 'Bot not found'}), 404
        
    try:
        data = request.json
        bot = BOTS_DB[bot_id]
        
        # Update bot data
        bot['name'] = data.get('name', bot['name'])
        
        # Log the action
        app.logger.info(f"Admin {session['username']} updated bot {bot_id}")
        
        return jsonify(bot)
        
    except Exception as e:
        app.logger.error(f'Error updating bot: {str(e)}')
        return jsonify({'error': 'Failed to update bot'}), 500

@app.route('/api/admin/bots/<bot_id>/toggle', methods=['POST'])
@admin_required
def toggle_bot(bot_id):
    """Toggle bot active status"""
    if bot_id not in BOTS_DB:
        return jsonify({'error': 'Bot not found'}), 404
        
    try:
        data = request.json
        bot = BOTS_DB[bot_id]
        
        # Toggle status
        bot['active'] = data.get('active', not bot['active'])
        
        # Log the action
        status = 'activated' if bot['active'] else 'deactivated'
        app.logger.info(f"Admin {session['username']} {status} bot {bot_id}")
        
        return jsonify(bot)
        
    except Exception as e:
        app.logger.error(f'Error toggling bot: {str(e)}')
        return jsonify({'error': 'Failed to toggle bot'}), 500

@app.route('/api/admin/bots/trade', methods=['POST'])
@admin_required
def force_trade():
    """Force trade between bot and user"""
    try:
        data = request.json
        bot_id = data.get('botId')
        user_id = data.get('userId')
        items = data.get('items', [])
        
        if not bot_id or not user_id:
            return jsonify({'error': 'Missing bot ID or user ID'}), 400
            
        if bot_id not in BOTS_DB:
            return jsonify({'error': 'Bot not found'}), 404
            
        if user_id not in USERS_DB:
            return jsonify({'error': 'User not found'}), 404
            
        bot = BOTS_DB[bot_id]
        user = USERS_DB[user_id]
        
        # In a real implementation, this would:
        # 1. Verify items exist in bot's inventory
        # 2. Create Steam trade offer
        # 3. Monitor trade status
        # 4. Update inventories when trade completes
        
        # For demo, just log the action
        app.logger.info(
            f"Admin {session['username']} forced trade: "
            f"Bot {bot_id} -> User {user_id}, Items: {len(items)}"
        )
        
        return jsonify({'message': 'Trade initiated successfully'})
        
    except Exception as e:
        app.logger.error(f'Error forcing trade: {str(e)}')
        return jsonify({'error': 'Failed to force trade'}), 500

# Maintenance mode configuration
MAINTENANCE_MODE = {
    'active': False,
    'settings': {
        'message': 'Site is under maintenance. Please check back later.',
        'duration': 30,  # minutes
        'allowAdminAccess': True,
        'startTime': None
    }
}

def maintenance_check():
    """Check if site is in maintenance mode"""
    if MAINTENANCE_MODE['active']:
        # Allow admin access if enabled
        if MAINTENANCE_MODE['settings']['allowAdminAccess'] and session.get('role') == 'admin':
            return
            
        # Return maintenance page for all other users
        return render_template('maintenance.html', 
            message=MAINTENANCE_MODE['settings']['message'],
            startTime=MAINTENANCE_MODE['settings']['startTime'],
            duration=MAINTENANCE_MODE['settings']['duration']
        ), 503

# Add maintenance check to all non-admin routes
@app.before_request
def check_maintenance():
    if not request.path.startswith('/admin') and not request.path.startswith('/static'):
        maintenance_response = maintenance_check()
        if maintenance_response:
            return maintenance_response

# Maintenance mode routes
@app.route('/admin/maintenance')
@admin_required
def maintenance_page():
    return app.send_static_file('admin/maintenance.html')

@app.route('/api/admin/maintenance/status')
@admin_required
def get_maintenance_status():
    """Get current maintenance status and stats"""
    return jsonify({
        'maintenanceMode': MAINTENANCE_MODE['active'],
        'settings': MAINTENANCE_MODE['settings'],
        'stats': {
            'activeUsers': len([u for u in USERS_DB.values() if u.get('status') == 'active']),
            'activeTrades': sum(1 for u in USERS_DB.values() for t in u.get('trades', []) 
                              if t['date'] > (datetime.utcnow() - timedelta(hours=1)).isoformat()),
            'activeBots': sum(1 for b in BOTS_DB.values() if b['active'])
        }
    })

@app.route('/api/admin/maintenance/toggle', methods=['POST'])
@admin_required
def toggle_maintenance():
    """Toggle maintenance mode"""
    try:
        data = request.json
        MAINTENANCE_MODE['active'] = data.get('active', not MAINTENANCE_MODE['active'])
        
        if MAINTENANCE_MODE['active']:
            MAINTENANCE_MODE['settings']['startTime'] = datetime.utcnow().isoformat()
        else:
            MAINTENANCE_MODE['settings']['startTime'] = None
        
        # Log the action
        status = 'enabled' if MAINTENANCE_MODE['active'] else 'disabled'
        app.logger.info(f"Admin {session['username']} {status} maintenance mode")
        
        return jsonify({
            'maintenanceMode': MAINTENANCE_MODE['active'],
            'settings': MAINTENANCE_MODE['settings']
        })
        
    except Exception as e:
        app.logger.error(f'Error toggling maintenance mode: {str(e)}')
        return jsonify({'error': 'Failed to toggle maintenance mode'}), 500

@app.route('/api/admin/maintenance/settings', methods=['POST'])
@admin_required
def update_maintenance_settings():
    """Update maintenance mode settings"""
    try:
        data = request.json
        
        MAINTENANCE_MODE['settings'].update({
            'message': data.get('message', MAINTENANCE_MODE['settings']['message']),
            'duration': data.get('duration', MAINTENANCE_MODE['settings']['duration']),
            'allowAdminAccess': data.get('allowAdminAccess', MAINTENANCE_MODE['settings']['allowAdminAccess'])
        })
        
        # Log the action
        app.logger.info(f"Admin {session['username']} updated maintenance settings")
        
        return jsonify({
            'maintenanceMode': MAINTENANCE_MODE['active'],
            'settings': MAINTENANCE_MODE['settings']
        })
        
    except Exception as e:
        app.logger.error(f'Error updating maintenance settings: {str(e)}')
        return jsonify({'error': 'Failed to update settings'}), 500

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not STEAM_API_KEY:
            return jsonify({'error': 'Steam API key not configured'}), 500
        return f(*args, **kwargs)
    return decorated_function

@require_api_key
def get_steam_user_info(steam_id):
    """Fetch user info from Steam API"""
    try:
        params = {
            'key': STEAM_API_KEY,
            'steamids': steam_id
        }
        response = requests.get(
            f'{STEAM_API_URL}/ISteamUser/GetPlayerSummaries/v2/',
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get('response', {}).get('players'):
            logger.error(f"No player data returned for Steam ID: {steam_id}")
            return None
            
        return data['response']['players'][0]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Steam user info: {str(e)}")
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Error parsing Steam API response: {str(e)}")
        return None

@require_api_key
def get_steam_inventory(steam_id):
    """Fetch CS2 inventory from Steam API"""
    try:
        params = {
            'key': STEAM_API_KEY,
            'steamid': steam_id,
            'appid': 730,  # CS2 App ID
            'contextid': 2  # Inventory context
        }
        response = requests.get(
            f'{STEAM_API_URL}/IEconService/GetInventoryItems/v1/',
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if 'result' not in data:
            logger.error(f"No inventory data returned for Steam ID: {steam_id}")
            return None
            
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Steam inventory: {str(e)}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing Steam API response: {str(e)}")
        return None

@app.route('/')
def index():
    if not STEAM_API_KEY:
        return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Steam API Configuration Required</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
                <div class="max-w-2xl mx-auto p-8 text-center">
                    <h1 class="text-3xl font-bold text-red-500 mb-4">Steam API Configuration Required</h1>
                    <p class="text-gray-300 mb-6">
                        To use this application, you need to configure a Steam Web API Key.
                        Please follow these steps:
                    </p>
                    <ol class="text-left text-gray-300 space-y-4 mb-8">
                        <li>1. Go to <a href="https://steamcommunity.com/dev/apikey" class="text-cyber-blue hover:underline" target="_blank">Steam Web API Key Registration</a></li>
                        <li>2. Log in with your Steam account if needed</li>
                        <li>3. Enter a domain name (can be localhost for testing)</li>
                        <li>4. Create a .env file in the project root with:</li>
                        <li class="bg-gray-800 p-4 rounded">
                            <code>STEAM_API_KEY=your_api_key_here</code>
                        </li>
                        <li>5. Restart the server</li>
                    </ol>
                    <p class="text-gray-400 text-sm">
                        Note: Keep your API key secure and never commit it to version control.
                    </p>
                </div>
            </body>
            </html>
        '''
    # Redirect to dashboard if authenticated
    if session.get('authenticated'):
        return redirect('/dashboard.html')
    return app.send_static_file('index.html')

@app.route('/dashboard.html')
@login_required
def dashboard():
    # Get user info from session
    user_info = session.get('user_info')
    steam_id = session.get('steam_id')
    
    if not user_info or not steam_id:
        session.clear()
        return redirect('/login.html')
        
    try:
        # Get fresh inventory data
        inventory = get_steam_inventory(steam_id)
        if not inventory:
            app.logger.error(f"Failed to fetch inventory for user {steam_id}")
            
        # Return dashboard with user data embedded
        return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Dashboard - CS2 SKINS</title>
                <script>
                    window.USER_DATA = {{
                        steamId: '{steam_id}',
                        userInfo: {json.dumps(user_info)},
                        inventory: {json.dumps(inventory) if inventory else 'null'}
                    }};
                </script>
            </head>
            <body>
                {app.send_static_file('dashboard.html').get_data(as_text=True)}
            </body>
            </html>
        '''
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        return redirect('/login.html?error=dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/auth/steam')
def auth_steam():
    """Initiate Steam OpenID authentication"""
    if not STEAM_API_KEY:
        app.logger.error("Steam API key not configured")
        return redirect('/login.html?error=api_key')

    try:
        # Rate limiting check
        ip = request.remote_addr
        current_time = time.time()
        if ip in auth_attempts:
            attempts = [t for t in auth_attempts[ip] if current_time - t < 3600]  # Last hour
            if len(attempts) >= 5:
                app.logger.warning(f"Rate limit exceeded for IP: {ip}")
                return redirect('/login.html?error=rate_limit')
            auth_attempts[ip] = attempts
        auth_attempts[ip] = auth_attempts.get(ip, []) + [current_time]

        # Get the current host and ensure proper protocol
        host = request.headers.get('Host', 'localhost:8000')
        protocol = 'https' if request.is_secure else 'http'
        base_url = f"{protocol}://{host}"
        
        # Validate return URL
        return_url = f"{base_url}/auth/steam/callback"
        if not return_url.startswith(('http://', 'https://')):
            raise ValueError("Invalid return URL scheme")
        
        # Generate and store state parameter to prevent CSRF
        state = os.urandom(16).hex()
        session['steam_auth_state'] = state
        
        # Configure Steam OpenID parameters with additional security
        params = {
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.mode': 'checkid_setup',
            'openid.return_to': return_url,
            'openid.realm': base_url,
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1',
            'openid.sreg.required': 'nickname,email',
            'openid.state': state,
            'openid.ts': str(int(time.time()))  # Add timestamp to prevent replay attacks
        }

        # Log authentication attempt
        app.logger.info(f"Initiating Steam auth with return URL: {params['openid.return_to']}")
        
        # Build and validate auth URL
        auth_url = STEAM_OPENID_URL + '?' + requests.compat.urlencode(params)
        if not auth_url.startswith(STEAM_OPENID_URL):
            raise ValueError("Invalid auth URL generated")

        return redirect(auth_url)

    except ValueError as e:
        app.logger.error(f"Validation error in Steam auth: {str(e)}")
        return redirect('/login.html?error=validation')
    except Exception as e:
        app.logger.error(f"Error initiating Steam auth: {str(e)}")
        return redirect('/login.html?error=auth_error')
=======
        return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Steam API Configuration Required</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
                <div class="max-w-2xl mx-auto p-8 text-center">
                    <h1 class="text-3xl font-bold text-red-500 mb-4">Steam API Configuration Required</h1>
                    <p class="text-gray-300 mb-6">
                        To use this application, you need to configure a Steam Web API Key.
                        Please follow these steps:
                    </p>
                    <ol class="text-left text-gray-300 space-y-4 mb-8">
                        <li>1. Go to <a href="https://steamcommunity.com/dev/apikey" class="text-cyber-blue hover:underline" target="_blank">Steam Web API Key Registration</a></li>
                        <li>2. Log in with your Steam account if needed</li>
                        <li>3. Enter a domain name (can be localhost for testing)</li>
                        <li>4. Create a .env file in the project root with:</li>
                        <li class="bg-gray-800 p-4 rounded">
                            <code>STEAM_API_KEY=your_api_key_here</code>
                        </li>
                        <li>5. Restart the server</li>
                    </ol>
                    <p class="text-gray-400 text-sm">
                        Note: Keep your API key secure and never commit it to version control.
                    </p>
                    <div class="mt-8">
                        <a href="/login.html" class="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors">
                            Return to Login
                        </a>
                    </div>
                </div>
            </body>
            </html>
        '''
    
        try:
            # Get the current host and ensure proper protocol
            host = request.headers.get('Host', 'localhost:8000')
            protocol = 'https' if request.is_secure else 'http'
            base_url = f"{protocol}://{host}"
            
            # Validate return URL
            return_url = f"{base_url}/auth/steam/callback"
            if not return_url.startswith(('http://', 'https://')):
                raise ValueError("Invalid return URL scheme")
            
            # Configure Steam OpenID parameters with additional security
            params = {
                'openid.ns': 'http://specs.openid.net/auth/2.0',
                'openid.mode': 'checkid_setup',
                'openid.return_to': return_url,
                'openid.realm': base_url,
                'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
                'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
                # Add nonce for additional security
                'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1',
                'openid.sreg.required': 'nickname,email',
                # Add timestamp to prevent replay attacks
                'openid.ts': str(int(time.time()))
            }

            # Generate and store state parameter to prevent CSRF
            state = os.urandom(16).hex()
            session['steam_auth_state'] = state
            params['openid.state'] = state

            # Rate limiting check
            ip = request.remote_addr
            current_time = time.time()
            if ip in auth_attempts:
                attempts = [t for t in auth_attempts[ip] if current_time - t < 3600]  # Last hour
                if len(attempts) >= 5:
                    app.logger.warning(f"Rate limit exceeded for IP: {ip}")
                    return redirect('/login.html?error=rate_limit')
                auth_attempts[ip] = attempts
            auth_attempts[ip] = auth_attempts.get(ip, []) + [current_time]

            # Log authentication attempt
            app.logger.info(f"Initiating Steam auth with return URL: {params['openid.return_to']}")
            
            # Build and validate auth URL
            auth_url = STEAM_OPENID_URL + '?' + requests.compat.urlencode(params)
            if not auth_url.startswith(STEAM_OPENID_URL):
                raise ValueError("Invalid auth URL generated")

            return redirect(auth_url)
        except ValueError as e:
            app.logger.error(f"Validation error in Steam auth: {str(e)}")
            return redirect('/login.html?error=validation')
        except Exception as e:
            app.logger.error(f"Error initiating Steam auth: {str(e)}")
        return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Error</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
                <div class="max-w-xl mx-auto p-8 text-center">
                    <h1 class="text-3xl font-bold text-red-500 mb-4">Authentication Error</h1>
                    <p class="text-gray-300 mb-6">
                        An error occurred while trying to authenticate with Steam. Please try again later.
                    </p>
                    <div class="text-left bg-gray-800 p-4 rounded mb-6">
                        <code class="text-red-400">{str(e)}</code>
                    </div>
                    <div class="flex justify-center space-x-4">
                        <a href="/" class="cyber-border px-6 py-3 rounded-md bg-black/50 hover:bg-cyber-blue/10 transition-all text-cyber-blue">
                            Return Home
                        </a>
                        <button onclick="window.location.reload()" class="cyber-border px-6 py-3 rounded-md bg-black/50 hover:bg-green-500/10 transition-all text-green-500">
                            Try Again
                        </button>
                    </div>
                </div>
            </body>
            </html>
        ''', 500

@app.route('/auth/steam/callback')
@require_api_key
def auth_steam_callback():
    """Handle Steam OpenID callback"""
    try:
        # Verify state parameter to prevent CSRF
        state = request.args.get('openid.state')
        if not state or state != session.get('steam_auth_state'):
            app.logger.warning("Invalid state parameter in Steam callback")
            return redirect('/login.html?error=invalid_state')

        # Get Steam ID from response
        steam_id = request.args.get('openid.claimed_id')
        if not steam_id:
            app.logger.error("Missing Steam ID in callback")
            return redirect('/login.html?error=no_steam_id')
        
        steam_id = steam_id.split('/')[-1]
        
        # Verify the response with Steam
        params = {
            'openid.assoc_handle': request.args.get('openid.assoc_handle'),
            'openid.signed': request.args.get('openid.signed'),
            'openid.sig': request.args.get('openid.sig'),
            'openid.ns': request.args.get('openid.ns'),
            'openid.mode': 'check_authentication'
        }
        
        # Copy signed parameters
        signed_params = request.args.get('openid.signed', '').split(',')
        for param in signed_params:
            value = request.args.get(f'openid.{param}')
            if value:
                params[f'openid.{param}'] = value
        
        # Verify with Steam
        try:
            response = requests.post(STEAM_OPENID_URL, data=params, timeout=10)
            if 'is_valid:true' not in response.text:
                return 'Invalid Steam authentication - Verification failed', 401
        except requests.exceptions.RequestException as e:
            return f'Steam authentication verification failed: {str(e)}', 500
        
        try:
            # Get user info from Steam API
            user_info = get_steam_user_info(steam_id)
            if not user_info:
                return 'Failed to fetch Steam user info', 500
            
            # Get or create user in our database
            if steam_id not in USERS_DB:
                USERS_DB[steam_id] = {
                    'steamId': steam_id,
                    'username': user_info['personaname'],
                    'role': 'user',
                    'status': 'active',
                    'avatarUrl': user_info['avatarfull'],
                    'totalTrades': 0,
                    'balance': 0.00,
                    'trades': [],
                    'loginHistory': []
                }
            
            user = USERS_DB[steam_id]
            
            # Check if user is banned
            if user['status'] == 'banned':
                return '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Account Banned</title>
                        <script src="https://cdn.tailwindcss.com"></script>
                    </head>
                    <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
                        <div class="max-w-md p-8 text-center">
                            <h1 class="text-3xl font-bold text-red-500 mb-4">Account Banned</h1>
                            <p class="text-gray-300 mb-6">
                                Your account has been banned. Please contact support for assistance.
                            </p>
                            <a href="/" class="inline-block px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors">
                                Return Home
                            </a>
                        </div>
                    </body>
                    </html>
                ''', 403
            
            # Update login history
            user['loginHistory'].append({
                'date': datetime.utcnow().isoformat() + 'Z',
                'ip': request.remote_addr,
                'location': 'Unknown'  # In production, use IP geolocation
            })
            
            # Store user data in session
            session['steam_id'] = steam_id
            session['user_info'] = user_info
            session['authenticated'] = True
            session['role'] = user['role']
            
            # Generate JWT token for API authentication
            token = generate_jwt_token(steam_id, user['role'])
            
            # Return success page with script to set session storage
            return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Steam Login Success</title>
                </head>
                <body>
                    <script>
                        try {{
                            sessionStorage.setItem('authenticated', 'true');
                            sessionStorage.setItem('user_role', '{user["role"]}');
                            sessionStorage.setItem('auth_token', '{token}');
                            window.location.href = '{"/admin/dashboard" if user["role"] in ["admin", "staff"] else "/dashboard.html"}';
                        }} catch (error) {{
                            console.error('Error storing auth data:', error);
                            window.location.href = '/login.html?error=storage';
                        }}
                    </script>
                </body>
                </html>
            '''
        except Exception as e:
            app.logger.error(f'Error processing Steam user data: {str(e)}')
            return 'Error processing Steam login data', 500
    except Exception as e:
        return str(e), 500

@app.route('/api/inventory/<steam_id>')
@require_api_key
def get_inventory(steam_id):
    """Get user's CS2 inventory"""
    try:
        inventory = get_steam_inventory(steam_id)
        return jsonify(inventory)
    except Exception as e:
        return str(e), 500

@app.route('/api/recent-drops')
@require_api_key
def get_recent_drops():
    """Get real recent drops from the system"""
    try:
        # In a real implementation, this would fetch from a database
        # For now, we'll fetch from Steam Market API
        params = {
            'key': STEAM_API_KEY,
            'appid': 730,
            'count': 10
        }
        response = requests.get(f'{STEAM_API_URL}/IEconMarket/GetPopular/v1/', params=params)
        return jsonify(response.json())
    except Exception as e:
        return str(e), 500

@app.route('/api/case/<case_id>/items')
@require_api_key
def get_case_items(case_id):
    """Get real items and probabilities for a case"""
    try:
        # In a real implementation, this would fetch from a database
        # For now, we'll fetch from Steam Market API
        params = {
            'key': STEAM_API_KEY,
            'appid': 730,
            'case': case_id
        }
        response = requests.get(f'{STEAM_API_URL}/IEconItems_730/GetItemsInCase/v1/', params=params)
        return jsonify(response.json())
    except Exception as e:
        return str(e), 500

@app.route('/api/trade/create', methods=['POST'])
@require_api_key
def create_trade():
    """Create a real Steam trade offer"""
    try:
        data = request.json
        steam_id = data.get('steamId')
        items_to_give = data.get('itemsToGive', [])
        items_to_receive = data.get('itemsToReceive', [])
        
        # In a real implementation, this would use Steam's trade offer API
        params = {
            'key': STEAM_API_KEY,
            'steamid_other': steam_id,
            'items_to_give': items_to_give,
            'items_to_receive': items_to_receive
        }
        response = requests.post(f'{STEAM_API_URL}/IEconService/CreateTradeOffer/v1/', json=params)
        return jsonify(response.json())
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(port=8000, debug=True)
