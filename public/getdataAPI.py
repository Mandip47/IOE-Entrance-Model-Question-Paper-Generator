import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("BASE_URL")
TOKEN = os.getenv("TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


def start_exam():
    """Make the first POST request to start the exam"""
    url = f"{BASE_URL}/mock-test/start-exam"

    try:
        response = requests.post(url, headers=HEADERS)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()
        session_id = data.get('examSessionId')
        questions = data.get('questions', [])
        questions_string = ','.join(map(str, questions))


        return session_id, questions_string

    except requests.exceptions.RequestException as e:
        print(f"Error in start_exam: {e}")
        return None, None


def get_questions(session_id, questions):
    """Make the second POST request to get questions"""
    url = f"{BASE_URL}/exam/questions"

    payload = {"sessionID": session_id, "questionIDs": questions}

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()

        data = response.json()
        return data

    except requests.exceptions.RequestException as e:
        print(f"Error in get_questions: {e}")
        return None


def getData():
    # Step 1: Start the exam and get session ID and questions
    session_id, questions = start_exam()

    if session_id and questions:
        # Step 2: Get questions details
        return get_questions(session_id, questions)
    else:
        print("Failed to get session ID and questions. Cannot proceed.")
