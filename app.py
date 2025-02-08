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
DEFAULT_DELAY_HOURS = 1
DEFAULT_DELAY_MINUTES = 5

# Store for scheduled tasks
scheduled_tasks = {}
task_history = defaultdict(list)

def parse_request_data(request):
    """Parse request data handling various formats."""
    try:
        # First, try to get the raw data as text
        raw_data = request.get_data(as_text=True)
        logger.info(f"Raw request data: {raw_data}")

        # Handle the case where the string contains literal \n characters
        if '\\n' in raw_data:
            # Remove the outer quotes if they exist
            if raw_data.startswith('"') and raw_data.endswith('"'):
                raw_data = raw_data[1:-1]
            
            # Replace literal \n with actual newlines
            raw_data = raw_data.replace('\\n', '\n')
            logger.info(f"After newline replacement: {raw_data}")

        # If it starts with "```json", it's a code block format
        if raw_data.startswith('```json'):
            # Strip the ```json and ``` markers and any whitespace
            json_str = raw_data.replace('```json', '').replace('```', '').strip()
            logger.info(f"Extracted JSON from code block: {json_str}")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse code block JSON: {e}")

        # Try parsing as regular JSON
        try:
            return json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse raw JSON: {e}")

        # If we have JSON in request.json, use that
        if request.is_json:
            return request.json

        # If we get here, we couldn't parse the data
        raise ValueError(f"Could not parse request data as JSON. Raw data: {raw_data}")

    except Exception as e:
        logger.error(f"Error parsing request data: {e}")
        raise

@app.route('/')
def home():
    """Root endpoint to verify server is running."""
    return jsonify({
        "status": "running",
        "message": "Webhook scheduler is running",
        "time": datetime.now().isoformat(),
        "env": os.environ.get('FLASK_ENV', 'production')
    })

def validate_iso_datetime(dt_string: str) -> Optional[datetime]:
    """Validate and parse ISO format datetime string."""
    try:
        # Try parsing the datetime string
        if dt_string.endswith('Z'):
            # Convert 'Z' timestamp to datetime
            # Remove the 'Z' and assume UTC
            dt_string = dt_string[:-1] + '+00:00'
        
        dt = datetime.fromisoformat(dt_string)
        logger.info(f"Successfully parsed datetime: {dt}")
        return dt
    except ValueError as e:
        logger.error(f"Invalid datetime format: {e}")
        logger.error(f"Received datetime string: {dt_string}")
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
    """Schedule a message to be sent later."""
    try:
        logger.info("Received schedule request")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        try:
            data = parse_request_data(request)
        except Exception as e:
            logger.error(f"Failed to parse request data: {e}")
            return jsonify({
                "status": "error",
                "message": "Invalid request data",
                "details": str(e)
            }), 400

        if not data:
            logger.error("No data received")
            return jsonify({
                "status": "error",
                "message": "No data received"
            }), 400

        logger.info(f"Parsed data: {data}")
        
        if 'appointment_time' not in data or 'formatted_message' not in data:
            logger.error(f"Missing required fields. Received fields: {list(data.keys())}")
            return jsonify({
                "status": "error",
                "message": "Missing required fields: appointment_time and formatted_message",
                "received_fields": list(data.keys())
            }), 400

        appointment_time_iso = data['appointment_time']
        formatted_message = data['formatted_message']
        
        logger.info(f"Received appointment_time: {appointment_time_iso}")
        logger.info(f"Received message: {formatted_message}")
        
        appointment_time = validate_iso_datetime(appointment_time_iso)
        
        if not appointment_time:
            return jsonify({
                "status": "error",
                "message": "Invalid datetime format. Please use ISO format (YYYY-MM-DDTHH:MM:SS+HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
                "received_time": appointment_time_iso
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
        
        logger.info(f"Successfully scheduled task {task_id} for {target_time}")
        
        return jsonify({
            "status": "success",
            "message": "Task scheduled successfully",
            "task_id": task_id,
            "details": {
                "original_time": appointment_time_iso,
                "scheduled_time": target_time.isoformat(),
                "formatted_message": formatted_message
            }
        }), 200

    except Exception as e:
        logger.exception("Error in schedule_message")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
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
