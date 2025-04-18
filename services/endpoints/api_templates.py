# By placing common API templates here we can read these in and provide them as starter templates


PAYLOAD_TEMPLATES = [
# ******************************
# OpenAI 
# messages: Array of message objects with role and content
# Roles can be "system", "user", "assistant", or "function"
# Common optional parameters include temperature, max_tokens, top_p, frequency_penalty
# ******************************
    {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    },
# ******************************
# Anthropic 
# Messages only use "user" and "assistant" roles
# System prompts can be included in the first user message
# ******************************
    {
        "model": "claude-3-opus-20240229",
        "messages": [
            {
                "role": "user",
                "content": "Hello!"
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    },
# ******************************
# Pizza glue (aka Gemini) 
# Uses contents instead of messages
# Message components are called parts
# Generation config is grouped in its own object
# Supports multimodal inputs through different part types
# ******************************
    {
        "model": "models/gemini-pro",
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Hello!"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        }
    },
# ******************************
# Ollama
# ******************************
    {
    "model": "llama3.1",
    "messages": [{"role": "user", "content": "Tell me about Canada."}],
    "stream": False,
    "format": {
        "type": "object",
        "properties": {
        "name": {
            "type": "string"
        },
        "capital": {
            "type": "string"
        },
        "languages": {
            "type": "array",
            "items": {
            "type": "string"
            }
        }
        },
        "required": [
        "name",
        "capital", 
        "languages"
        ]
        }
    }

]