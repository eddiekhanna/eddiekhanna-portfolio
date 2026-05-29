from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import hmac
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from openai import OpenAI
from system_prompts import get_prompt
from pushover_complete import PushoverAPI
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from supabase import create_client


# Load environment variables
load_dotenv(override=True)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'dev-secret-key-change-in-production'
app.config['DEBUG'] = os.getenv('FLASK_ENV') == 'development'
app.config['PORT'] = int(os.getenv('PORT', 5001))

# Frontend URL for AI to suggest links
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')

# Initialize DeepSeek client
deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
# DeepSeek's OpenAI-compatible SDK expects the API root, not the versioned path
deepseek = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com") if deepseek_api_key else None

# Enable CORS
CORS(app)

# Supabase client (used for the thoughts table)
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Token serializer for the thoughts admin login
auth_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='thoughts-auth')
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24  # 24 hours

def verify_auth_token(token: str) -> bool:
    if not token:
        return False
    try:
        auth_serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or malformed Authorization header'}), 401
        token = auth_header[len('Bearer '):]
        if not verify_auth_token(token):
            return jsonify({'error': 'Invalid or expired token'}), 401
        return fn(*args, **kwargs)
    return wrapper

# Global variable to store the system prompt
system_prompt = None

@app.route('/api/login', methods=['POST'])
def login():
    """Verify the admin password and return a signed token."""
    try:
        data = request.get_json() or {}
        password = data.get('password', '')
        expected = os.getenv('THOUGHTS_PASSWORD')

        if not expected:
            print("❌ THOUGHTS_PASSWORD not configured")
            return jsonify({'error': 'Login not configured'}), 500

        if not hmac.compare_digest(password, expected):
            return jsonify({'error': 'Invalid password'}), 401

        token = auth_serializer.dumps({'role': 'admin'})
        return jsonify({'token': token, 'expires_in': TOKEN_MAX_AGE_SECONDS})

    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return jsonify({'error': f'Login error: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Stateless logout — the frontend discards its token."""
    return jsonify({'success': True})

@app.route('/api/thoughts', methods=['GET'])
def list_thoughts():
    """Public — list thoughts for a given year and month, ordered chronologically."""
    try:
        if not supabase:
            return jsonify({'error': 'Supabase not configured'}), 500

        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        if not year or not month:
            return jsonify({'error': 'year and month query params are required'}), 400

        result = (
            supabase.table('thoughts')
            .select('*')
            .eq('year', year)
            .eq('month', month)
            .order('time', desc=False)
            .execute()
        )
        return jsonify({'thoughts': result.data or []})

    except Exception as e:
        print(f"❌ List thoughts error: {str(e)}")
        return jsonify({'error': f'Failed to list thoughts: {str(e)}'}), 500

@app.route('/api/thoughts', methods=['POST'])
@require_auth
def create_thought():
    """Auth-required — insert a new thought."""
    try:
        if not supabase:
            return jsonify({'error': 'Supabase not configured'}), 500

        data = request.get_json() or {}
        text = (data.get('text') or '').strip()
        time_iso = data.get('time')

        if not text or not time_iso:
            return jsonify({'error': 'text and time are required'}), 400

        try:
            dt = datetime.fromisoformat(time_iso.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid time format; expected ISO 8601'}), 400

        row = {
            'text': text,
            'year': dt.year,
            'month': dt.month,
            'time': dt.isoformat(),
        }
        result = supabase.table('thoughts').insert(row).execute()
        return jsonify({'thought': result.data[0] if result.data else None}), 201

    except Exception as e:
        print(f"❌ Create thought error: {str(e)}")
        return jsonify({'error': f'Failed to create thought: {str(e)}'}), 500

@app.route('/api/ai/initialize', methods=['POST'])
def initialize_ai():
    """Initialize AI with a system prompt"""
    global system_prompt
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        prompt_type = data.get('prompt_type', 'default')
        
        print(f"🔧 Initializing AI with prompt type: {prompt_type}")
        
        # Check if API key is available
        if not deepseek:
            print("❌ DeepSeek API key not configured")
            return jsonify({'error': 'DeepSeek API key not configured'}), 500
        
        # Get system prompt and add frontend URL
        base_prompt = get_prompt(prompt_type)
        system_prompt = base_prompt.replace('{FRONTEND_URL}', FRONTEND_URL)
        
        print(f"✅ AI initialized successfully")
        print(f"📝 System prompt length: {len(system_prompt)} characters")
        print(f"🌐 Frontend URL: {FRONTEND_URL}")
        
        return jsonify({
            'message': 'AI initialized successfully',
            'prompt_type': prompt_type,
            'frontend_url': FRONTEND_URL
        })
        
    except Exception as e:
        print(f"❌ Initialization error: {str(e)}")
        return jsonify({'error': f'Initialization error: {str(e)}'}), 500

@app.route('/api/ai/chat', methods=['POST'])
def chat_with_ai():
    """Send a message to the AI and get response"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        print(f"💬 Received user message: {message}")
        
        if not system_prompt:
            print("❌ AI not initialized")
            return jsonify({'error': 'AI not initialized. Call /api/ai/initialize first'}), 400
        
        response = chat(message)
        print(f"🤖 AI response: {response}")
        
        return jsonify({'response': response})
            
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        return jsonify({'error': f'Chat error: {str(e)}'}), 500

def chat(message):
    """Function that takes a message and returns the LLM response"""
    try:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
        print(f"📤 Sending to DeepSeek API...")
        response = deepseek.chat.completions.create(
            model="deepseek-chat", 
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        ai_response = response.choices[0].message.content
        print(f"📥 Received from DeepSeek API")
        return ai_response
        
    except Exception as e:
        print(f"❌ DeepSeek API error: {str(e)}")
        raise Exception(f'DeepSeek API error: {str(e)}')

@app.route('/api/contact', methods=['POST'])
def contact():
    """Handle contact form submissions and send Pushover notification"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        # Validate required fields
        if not name or not email or not message:
            return jsonify({'error': 'Name, email, and message are required'}), 400
        
        # Get Pushover configuration from environment
        pushover_token = os.getenv('PUSHOVER_TOKEN')
        pushover_user = os.getenv('PUSHOVER_USER')
        
        if not pushover_token or not pushover_user:
            print("❌ Pushover configuration missing")
            return jsonify({'error': 'Notification service not configured'}), 500
        
        # Create Pushover client (token is the app token)
        client = PushoverAPI(pushover_token)
        
        # Format notification message
        notification_title = f"New Contact Message from {name}"
        notification_message = f"""
From: {name}
Email: {email}

Message:
{message}
        """.strip()
        
        # Send notification (user is the user token)
        client.send_message(pushover_user, notification_message, title=notification_title)
        
        print(f"✅ Contact notification sent for: {name} ({email})")
        
        return jsonify({
            'message': 'Message sent successfully! I\'ll get back to you soon.',
            'success': True
        })
        
    except Exception as e:
        print(f"❌ Contact error: {str(e)}")
        return jsonify({'error': f'Failed to send message: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(
        debug=app.config['DEBUG'],
        host='0.0.0.0',
        port=app.config['PORT']
    ) 