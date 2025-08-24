from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
from system_prompts import get_prompt
from pushover_complete import PushoverAPI


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
deepseek = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com/v1") if deepseek_api_key else None

# Enable CORS
CORS(app)

# Global variable to store the system prompt
system_prompt = None

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