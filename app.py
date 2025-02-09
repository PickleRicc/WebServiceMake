from flask import Flask, jsonify
import requests
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
WEBHOOK_URL = 'https://hook.us2.make.com/cgbzb6ghpj0acg7kqnlfvw63m5ybp9pg'

@app.route('/test-webhook', methods=['GET'])
def test_webhook():
    """Test the webhook connection."""
    try:
        # Prepare webhook data
        webhook_data = {
            "data": {
                "message": "Hello from Flask!",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Send to webhook
        response = requests.post(WEBHOOK_URL, json=webhook_data)
        
        return jsonify({
            "status": "success",
            "webhook_response": response.text
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/')
def home():
    """Home endpoint to verify server is running."""
    return jsonify({
        "status": "running",
        "message": "Server is running"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)