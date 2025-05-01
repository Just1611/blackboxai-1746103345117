from flask import Blueprint, request, session, redirect, jsonify
from functools import wraps
import requests
import os
import time
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Store login attempts for rate limiting
auth_attempts = {}

# Create blueprint
steam_bp = Blueprint('steam', __name__)

# Steam OpenID configuration
STEAM_OPENID_URL = 'https://steamcommunity.com/openid/login'

def init_steam_auth(app, api_key, users_db, generate_token):
    """Initialize Steam authentication with app context"""
    global STEAM_API_KEY, USERS_DB, generate_jwt_token
    STEAM_API_KEY = api_key
    USERS_DB = users_db
    generate_jwt_token = generate_token
    app.register_blueprint(steam_bp)

def require_api_key(f):
    """Decorator to ensure Steam API key is configured"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not STEAM_API_KEY:
            return jsonify({'error': 'Steam API key not configured'}), 500
        return f(*args, **kwargs)
    return decorated_function

@steam_bp.route('/auth/steam')
def auth_steam():
    """Initiate Steam OpenID authentication"""
    if not STEAM_API_KEY:
        logger.error("Steam API key not configured")
        return redirect('/login.html?error=api_key')

    try:
        # Rate limiting check
        ip = request.remote_addr
        current_time = time.time()
        if ip in auth_attempts:
            attempts = [t for t in auth_attempts[ip] if current_time - t < 3600]  # Last hour
            if len(attempts) >= 5:
                logger.warning(f"Rate limit exceeded for IP: {ip}")
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
        logger.info(f"Initiating Steam auth with return URL: {params['openid.return_to']}")
        
        # Build and validate auth URL
        auth_url = STEAM_OPENID_URL + '?' + requests.compat.urlencode(params)
        if not auth_url.startswith(STEAM_OPENID_URL):
            raise ValueError("Invalid auth URL generated")

        return redirect(auth_url)

    except ValueError as e:
        logger.error(f"Validation error in Steam auth: {str(e)}")
        return redirect('/login.html?error=validation')
    except Exception as e:
        logger.error(f"Error initiating Steam auth: {str(e)}")
        return redirect('/login.html?error=auth_error')

@steam_bp.route('/auth/steam/callback')
@require_api_key
def auth_steam_callback():
    """Handle Steam OpenID callback"""
    try:
        # Clear any existing session data
        session.clear()

        # Verify state parameter to prevent CSRF
        state = request.args.get('openid.state')
        stored_state = session.pop('steam_auth_state', None)
        if not state or state != stored_state:
            logger.warning("Invalid state parameter in Steam callback")
            return redirect('/login.html?error=invalid_state')

        # Get Steam ID from response
        steam_id = request.args.get('openid.claimed_id')
        if not steam_id:
            logger.error("Missing Steam ID in callback")
            return redirect('/login.html?error=no_steam_id')
        
        steam_id = steam_id.split('/')[-1]

        # Clear rate limiting for successful login
        ip = request.remote_addr
        if ip in auth_attempts:
            del auth_attempts[ip]

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
                logger.error("Steam verification failed")
                return redirect('/login.html?error=verification_failed')
        except requests.exceptions.RequestException as e:
            logger.error(f"Steam verification request failed: {str(e)}")
            return redirect('/login.html?error=verification_error')
        
        try:
            # Get user info from Steam API
            user_info = get_steam_user_info(steam_id)
            if not user_info:
                logger.error("Failed to fetch Steam user info")
                return redirect('/login.html?error=user_info_failed')
            
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
                logger.warning(f"Banned user attempted login: {steam_id}")
                return redirect('/login.html?error=account_banned')
            
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
            logger.error(f'Error processing Steam user data: {str(e)}')
            return redirect('/login.html?error=processing_failed')
    except Exception as e:
        logger.error(f'Steam callback error: {str(e)}')
        return redirect('/login.html?error=callback_failed')
