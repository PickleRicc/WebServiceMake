from flask import Flask, request, jsonify
import requests
import schedule
import time
from datetime import datetime, timedelta
import logging
import os
from typing import Optional
import uuid
from collections import defaultdict
import json
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://hook.us2.make.com/u3ceaj53fe1o6lp0wy4piat5gl0im6oa')
DELAY_SECONDS = 30

# Store for scheduled tasks
scheduled_tasks = {}
task_history = defaultdict(list)

def send_delayed_message(task_id: str, message: str):
    """Send a message after a delay."""
    print(f"Starting delay for task {task_id}")  # Console logging
    logger.info(f"Starting delay for task {task_id}")
    logger.info(f"Will send message in {DELAY_SECONDS} seconds")
    logger.info(f"Using webhook URL: {WEBHOOK_URL}")
    
    time.sleep(DELAY_SECONDS)
    
    try:
        webhook_data = {
            "type": "delayed_message",
            "task_id": task_id,
            "content": message,
            "timestamp": datetime.now().isoformat(),
            "status": "delivered",
            "delay_seconds": DELAY_SECONDS
        }
        
        print(f"Sending to webhook: {webhook_data}")  # Console logging
        logger.info(f"Attempting to send to webhook URL: {WEBHOOK_URL}")
        logger.info(f"Webhook data: {webhook_data}")
        
        response = requests.post(WEBHOOK_URL, json=webhook_data)
        
        print(f"Webhook response: Status={response.status_code}, Body={response.text}")  # Console logging
        logger.info(f"Webhook response status: {response.status_code}")
        logger.info(f"Webhook response body: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending to webhook: {e}")  # Console logging
        logger.error(f"Error sending message for task {task_id}: {e}")
        return False

@app.route('/')
def home():
    """Root endpoint to verify server is running."""
    return jsonify({
        "status": "running",
        "message": "Webhook scheduler is running",
        "time": datetime.now().isoformat(),
        "env": os.environ.get('FLASK_ENV', 'production')
    })

@app.route('/test-webhook', methods=['GET'])
def test_webhook():
    """Test the webhook connection immediately."""
    try:
        # Send a test message immediately
        test_message = {
            "type": "test_message",
            "content": "Test message - checking webhook connection",
            "timestamp": datetime.now().isoformat(),
            "status": "test"
        }
        
        logger.info(f"Sending test message to webhook: {WEBHOOK_URL}")
        logger.info(f"Test message content: {test_message}")
        
        response = requests.post(WEBHOOK_URL, json=test_message)
        
        logger.info(f"Webhook response status: {response.status_code}")
        logger.info(f"Webhook response text: {response.text}")
        
        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "Webhook test successful",
                "response": response.text
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Webhook test failed with status {response.status_code}",
                "response": response.text
            }), 400
    
    except Exception as e:
        logger.exception("Error testing webhook")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/schedule', methods=['POST'])
def schedule_message():
    """Schedule a message to be sent after 30 seconds."""
    try:
        logger.info("Received schedule request")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        try:
            data = request.get_json()
        except Exception as e:
            logger.error(f"Failed to parse request data: {e}")
            return jsonify({
                "status": "error",
                "message": "Invalid request data",
                "details": str(e)
            }), 400

        if not data or 'formatted_message' not in data:
            logger.error("No message received")
            return jsonify({
                "status": "error",
                "message": "Message is required"
            }), 400

        formatted_message = data['formatted_message']
        task_id = str(uuid.uuid4())
        
        # Start a new thread to handle the delayed message
        thread = threading.Thread(
            target=send_delayed_message,
            args=(task_id, formatted_message)
        )
        thread.start()
        
        logger.info(f"Started delay thread for task {task_id}")
        
        return jsonify({
            "status": "success",
            "message": f"Message will be sent in {DELAY_SECONDS} seconds",
            "task_id": task_id,
            "details": {
                "message": formatted_message,
                "scheduled_time": (datetime.now() + timedelta(seconds=DELAY_SECONDS)).isoformat()
            }
        }), 200

    except Exception as e:
        logger.exception("Error in schedule_message")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
