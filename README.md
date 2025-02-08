# Webhook Scheduler

A Flask application that schedules and sends webhook requests to Make.com scenarios.

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

## Deployment to Render.com

1. Create a new account on [Render.com](https://render.com)
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Fill in the following details:
   - Name: webhook-scheduler (or your preferred name)
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Click "Create Web Service"

## API Endpoints

### Schedule a Message
```http
POST /schedule
Content-Type: application/json

{
    "appointment_time": "2025-02-08T16:00:00-05:00",
    "formatted_message": "Your message here"
}
```

### Check Status
```http
GET /status
GET /status?task_id=your_task_id
```
