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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://hook.us2.make.com/u3ceaj53fe1o6lp0wy4piat5gl0im6oa')
DEFAULT_DELAY_HOURS = 1
DEFAULT_DELAY_MINUTES = 5

# Store for scheduled tasks
scheduled_tasks = {}
task_history = defaultdict(list)

def validate_iso_datetime(dt_string: str) -> Optional[datetime]:
    """Validate and parse ISO format datetime string."""
    try:
        return datetime.fromisoformat(dt_string)
    except ValueError as e:
        logger.error(f"Invalid datetime format: {e}")
        return None

def send_request(task_id: str, formatted_message: str):
    """Send HTTP request to the webhook URL with the formatted message."""
    try:
        logger.info(f"Sending request for task {task_id}")
        response = requests.post(
            WEBHOOK_URL,
            json={
                "formatted_message": formatted_message
            },
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Request sent successfully for task {task_id}: {response.status_code}")
        task_history[task_id].append({
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'response_code': response.status_code
        })
        return True
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to send request for task {task_id}: {e}"
        logger.error(error_msg)
        task_history[task_id].append({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        })
        return False

@app.route('/schedule', methods=['POST'])
def schedule_message():
    try:
        data = request.json
        if not data or 'appointment_time' not in data or 'formatted_message' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: appointment_time and formatted_message"
            }), 400

        appointment_time_iso = data['appointment_time']
        formatted_message = data['formatted_message']
        
        appointment_time = validate_iso_datetime(appointment_time_iso)
        
        if not appointment_time:
            return jsonify({
                "status": "error",
                "message": "Invalid datetime format. Please use ISO format (YYYY-MM-DDTHH:MM:SS+HH:MM)"
            }), 400

        # Calculate target time
        target_time = appointment_time + timedelta(
            hours=DEFAULT_DELAY_HOURS,
            minutes=DEFAULT_DELAY_MINUTES
        )

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Create a closure to capture the formatted_message and task_id
        def scheduled_task():
            return send_request(task_id, formatted_message)

        # Schedule the request
        job = schedule.every().day.at(target_time.strftime("%H:%M")).do(scheduled_task)
        
        # Store task information
        scheduled_tasks[task_id] = {
            'job': job,
            'original_time': appointment_time_iso,
            'scheduled_time': target_time.isoformat(),
            'formatted_message': formatted_message,
            'status': 'scheduled'
        }
        
        task_history[task_id].append({
            'timestamp': datetime.now().isoformat(),
            'status': 'scheduled',
            'scheduled_time': target_time.isoformat()
        })
        
        logger.info(f"Scheduled task {task_id} for {target_time} with message: {formatted_message[:50]}...")
        
        return jsonify({
            "status": "success",
            "message": "Task scheduled successfully",
            "task_id": task_id,
            "details": {
                "original_time": appointment_time_iso,
                "scheduled_time": target_time.isoformat(),
                "formatted_message": formatted_message,
                "webhook_configured": bool(WEBHOOK_URL != 'https://hook.us2.make.com/u3ceaj53fe1o6lp0wy4piat5gl0im6oa')
            }
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Get status of all scheduled tasks or a specific task."""
    task_id = request.args.get('task_id')
    
    if task_id:
        if task_id not in scheduled_tasks:
            return jsonify({
                "status": "error",
                "message": "Task not found"
            }), 404
            
        task = scheduled_tasks[task_id]
        history = task_history[task_id]
        
        return jsonify({
            "task_id": task_id,
            "status": task['status'],
            "details": task,
            "history": history
        })
    
    # Return all tasks if no specific task_id provided
    return jsonify({
        "tasks": {
            task_id: {
                "status": task['status'],
                "details": task,
                "history": task_history[task_id]
            }
            for task_id, task in scheduled_tasks.items()
        }
    })

@app.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Test endpoint to immediately send a message to Make.com"""
    try:
        data = request.json
        message = data.get('formatted_message', 'Test message from webhook scheduler')
        
        response = requests.post(
            WEBHOOK_URL,
            json={
                "formatted_message": message
            },
            timeout=10
        )
        response.raise_for_status()
        
        return jsonify({
            "status": "success",
            "message": "Test message sent successfully",
            "response_code": response.status_code
        }), 200
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to send test message: {str(e)}"
        }), 500

def run_scheduler():
    """Run the scheduler in a separate thread."""
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Start the scheduler in a separate thread
    import threading
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
