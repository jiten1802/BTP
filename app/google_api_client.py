from json import load
import os
import base64
import logging
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict
import html2text
from datetime import datetime, timedelta
import pytz 
from dotenv import load_dotenv

# These are the Google libraries you installed
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup basic logging to see success/error messages in your terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define the permission scope. We are only asking to SEND emails, not read or delete them.
# This is a best practice for security (least privilege).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_sender_email() -> str:
    """Load and return the sender email from environment or .env each call."""
    load_dotenv()
    return os.getenv("SENDERS_EMAIL", "")

# Define paths relative to your project's root directory
# This ensures the code can find your credential files
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token.json' # This file will be created automatically

def get_gmail_service():
    """
    Authenticates with the Google Gmail API using OAuth 2.0.
    Handles the creation and refreshing of a token.json file.
    Returns an authorized Gmail service object.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    # It's created automatically when the authorization flow completes for the first time.
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # If the token is just expired, refresh it automatically without user interaction.
            creds.refresh(Request())
        else:
            # This is the one-time step: trigger the browser authentication flow.
            # It uses your credentials.json to know which app is asking for permission.
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run so this login process doesn't repeat.
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    # Build and return the service object that can make API calls
    return build('gmail', 'v1', credentials=creds)

def create_message(sender: str, to: str, subject: str, message_text: str) -> dict:
    """
    Creates an email message body formatted for the Gmail API.
    """
    # Create a standard email message object
    message = MIMEText(message_text, 'html')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    # The Gmail API requires the message to be encoded into a URL-safe base64 string
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': encoded_message}

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Sends an email using the authorized Gmail service.

    This is the main function that the Communicator agent will call.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    sender_email = get_sender_email()
    if not sender_email:
        logging.error("SENDER_EMAIL is not configured in environment variables.")
        return False
    if not CREDENTIALS_PATH.exists():
        logging.error(f"FATAL: credentials.json not found at {CREDENTIALS_PATH}. Please download it from Google Cloud Console.")
        return False

    try:
        # 1. Get an authenticated service object
        service = get_gmail_service()
        
        # 2. Prepare the email message
        message = create_message(sender_email, to_email, subject, html_content)
        
        # 3. Call the Gmail API to send the message
        sent_message = service.users().messages().send(
            userId="me",  # 'me' is a special keyword for the authenticated user
            body=message
        ).execute()
        
        logging.info(f"Email successfully sent to {to_email}. Message ID: {sent_message['id']}")
        return {"success": True, "message_id": sent_message['id'], "thread_id": sent_message['threadId']}
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        return {"success": False}

    except HttpError as error:
        logging.error(f"An HTTP error occurred while sending email to {to_email}: {error}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending email to {to_email}: {e}")
        return False
    
def search_for_replies(sender_email: str) -> List[Dict]:
    """
    Searches for unread emails from a specific sender address.
    
    Returns:
        A list of message summary dictionaries (e.g., [{'id': '...', 'threadId': '...'}])
    """
    try:
        service = get_gmail_service()
        # Query for unread messages from the specified sender
        query = f"from:{sender_email} is:unread"
        response = service.users().messages().list(userId="me", q=query).execute()
        return response.get('messages', [])
    except Exception as e:
        logging.error(f"Failed to search for replies from {sender_email}: {e}")
        return []

def get_message_details(message_id: str) -> Dict:
    """
    Gets the full details of a specific message, including a clean body text.
    """
    try:
        service = get_gmail_service()
        message = service.users().messages().get(userId="me", id=message_id, format='full').execute()
        
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        
        details = {
            'id': message.get('id'),
            'snippet': message.get('snippet'),
            'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), ''),
            'sender': next((h['value'] for h in headers if h['name'].lower() == 'from'), ''),
            'body': ''
        }

        # Recursively parse the body to find plain text or HTML content
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    body_data = part.get('body', {}).get('data', '')
                    details['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break # Prefer plain text
                elif part.get('mimeType') == 'text/html':
                    body_data = part.get('body', {}).get('data', '')
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    details['body'] = html2text.html2text(html_body) # Convert HTML to clean text
        elif 'body' in payload: # Non-multipart email
            body_data = payload.get('body', {}).get('data', '')
            details['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')

        return details
    except Exception as e:
        logging.error(f"Failed to get message details for ID {message_id}: {e}")
        return {}

def mark_as_read(message_id: str):
    """
    Marks a message as read by removing the 'UNREAD' label from it.
    """
    try:
        service = get_gmail_service()
        # This API call modifies the labels on the message
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    except Exception as e:
        logging.error(f"Failed to mark message {message_id} as read: {e}")

# Add these functions to the end of app/google_api_client.py

def get_calendar_service():
    """
    Returns an authorized Google Calendar service object.
    It uses the same underlying authentication as the Gmail service.
    """
    # The get_gmail_service function can be renamed to get_google_service
    # but for now, we can just call it as it handles the auth flow correctly.
    creds = get_gmail_service()._http.credentials
    return build('calendar', 'v3', credentials=creds)

def find_free_slots(start_date: datetime, end_date: datetime, duration_minutes: int = 30) -> List[Dict]:
    """
    Finds available time slots on the primary calendar within a given date range.
    """
    try:
        service = get_calendar_service()
        
        # Get the user's primary timezone
        user_timezone = service.settings().get(setting='timezone').execute()['value']
        tz = pytz.timezone(user_timezone)

        # Query for all busy events in the time range
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        busy_slots = events_result.get('items', [])

        # Define business hours (e.g., 9am to 5pm in user's timezone)
        business_start_hour = 9
        business_end_hour = 17
        
        free_slots = []
        
        # Start checking from the beginning of the range
        current_time = start_date.astimezone(tz)

        while current_time < end_date.astimezone(tz):
            # Only check within business hours and on weekdays
            if current_time.weekday() < 5 and business_start_hour <= current_time.hour < business_end_hour:
                slot_end_time = current_time + timedelta(minutes=duration_minutes)
                
                is_busy = False
                for event in busy_slots:
                    event_start = datetime.fromisoformat(event['start'].get('dateTime')).astimezone(tz)
                    event_end = datetime.fromisoformat(event['end'].get('dateTime')).astimezone(tz)
                    # Check for overlap
                    if max(current_time, event_start) < min(slot_end_time, event_end):
                        is_busy = True
                        break
                
                if not is_busy:
                    free_slots.append({
                        "start": current_time.isoformat(),
                        "end": slot_end_time.isoformat()
                    })
                    # If we found 3 slots, that's enough to propose
                    if len(free_slots) >= 3:
                        return free_slots

            # Move to the next 30-minute slot
            current_time += timedelta(minutes=30)
            
        return free_slots

    except Exception as e:
        logging.error(f"Failed to find free slots: {e}")
        return []

def create_calendar_event(summary: str, start_time: str, end_time: str, attendees: List[str], description: str = "") -> Dict:
    """
    Creates a new event on the primary calendar.
    """
    try:
        service = get_calendar_service()
        user_timezone = service.settings().get(setting='timezone').execute()['value']

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': user_timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': user_timezone,
            },
            'attendees': [{'email': email} for email in attendees],
            'reminders': {
                'useDefault': True,
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event, sendUpdates="all").execute()
        logging.info(f"Event created: {created_event.get('htmlLink')}")
        return created_event

    except Exception as e:
        logging.error(f"Failed to create calendar event: {e}")
        return {}
        
def send_reply_in_thread(thread_id: str, to_email: str, body: str) -> bool:
    """Sends a reply within an existing email thread."""
    try:
        service = get_gmail_service()
        # To send a reply, you need to find the headers of the original message
        original_message = service.users().messages().get(userId='me', id=thread_id).execute()
        original_headers = original_message['payload']['headers']
        
        original_subject = next(h['value'] for h in original_headers if h['name'].lower() == 'subject')

        SENDER_EMAIL = get_sender_email()
        message = MIMEText(body, 'html')
        message['to'] = to_email
        message['from'] = SENDER_EMAIL
        message['subject'] = original_subject 
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        reply_body = {'raw': raw_message, 'threadId': thread_id}
        
        sent_message = service.users().messages().send(userId='me', body=reply_body).execute()
        logging.info(f"Reply sent in thread {thread_id}.")
        return True
    except Exception as e:
        logging.error(f"Failed to send reply in thread {thread_id}: {e}")
        return False
