# Flask API Backend

A simple Flask API backend for your portfolio project with DeepSeek AI integration using the OpenAI client library.

## Setup

1. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the backend directory with:

   ```bash
   # Flask Configuration
   FLASK_APP=app.py
   FLASK_ENV=development
   PORT=5000
   SECRET_KEY=your-secret-key-here

   # DeepSeek API Key
   DEEPSEEK_API_KEY=your-deepseek-api-key-here
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

The API will be available at `http://localhost:5000`

## API Endpoints

### AI Integration (Two-Step Process)

#### 1. Initialize AI

- **POST** `/api/ai/initialize`
- Initialize AI with a system prompt

**Request Body:**

```json
{
  "prompt_type": "portfolio" // Optional: default, code_review, portfolio, interview, project
}
```

**Response:**

```json
{
  "message": "AI initialized successfully",
  "prompt_type": "portfolio",
  "system_prompt": "You are an AI assistant helping with a personal portfolio website..."
}
```

#### 2. Chat with AI

- **POST** `/api/ai/chat`
- Send a message to the initialized AI and get response

**Request Body:**

```json
{
  "message": "Your message here"
}
```

**Response:**

```json
{
  "response": "AI response here",
  "prompt_type": "portfolio",
  "model": "deepseek-chat"
}
```

#### Additional AI Endpoints

- **GET** `/api/ai/prompts` - Get available system prompt types
- **GET** `/api/ai/status` - Get current AI session status
- **POST** `/api/ai/reset` - Reset the AI session

## System Prompts

The API includes several pre-configured system prompts:

- **default**: General helpful assistant
- **code_review**: Expert code reviewer and developer
- **portfolio**: Portfolio-specific assistance
- **interview**: Technical interview preparation
- **project**: Software project brainstorming

## Development

- The API runs in debug mode by default
- CORS is enabled for all routes
- The server runs on port 5000 (configurable via PORT environment variable)
- Uses DeepSeek API with OpenAI client library
- AI session is maintained server-side until reset

## Project Structure

```
backend/
├── app.py              # Main Flask application
├── config.py           # Configuration and environment variables
├── system_prompts.py   # System prompt definitions
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Testing the API

You can test the endpoints using curl:

```bash
# Initialize AI
curl -X POST http://localhost:5000/api/ai/initialize \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "portfolio"}'

# Chat with initialized AI
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, can you help me with a React project?"}'

# Get AI status
curl http://localhost:5000/api/ai/status

# Reset AI session
curl -X POST http://localhost:5000/api/ai/reset

# Get available prompts
curl http://localhost:5000/api/ai/prompts
```

## Frontend Integration Example

```javascript
// Step 1: Initialize AI
const initResponse = await fetch("http://localhost:5000/api/ai/initialize", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    prompt_type: "portfolio",
  }),
});

// Step 2: Chat with AI
const chatResponse = await fetch("http://localhost:5000/api/ai/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "Help me improve my React portfolio",
  }),
});

const result = await chatResponse.json();
console.log(result.response);
```

## Environment Variables

- `DEEPSEEK_API_KEY`: Your DeepSeek API key (required)
- `FLASK_ENV`: Set to "development" for debug mode
- `PORT`: Server port (default: 5000)
- `SECRET_KEY`: Flask secret key (optional, has default)
