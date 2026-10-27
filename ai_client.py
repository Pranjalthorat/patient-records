"""Calls the Google Gemini API to get a short health remark for a patient."""
import os
from datetime import date

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_SECONDS = 30


class AIServiceError(Exception):
    """Raised when a prediction could not be obtained. The message is safe to show to users."""


def _age(date_of_birth):
    born = date.fromisoformat(date_of_birth)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def build_prompt(patient):
    return (
        "You are supporting a basic health-screening tool. Using only the blood test "
        "results below, name the most likely health condition or risk they point to "
        "(for example diabetes risk, anaemia, high cholesterol), or say the values look "
        "normal. Mention every value that is outside the usual adult range. The patient's "
        "sex is not known, so use general adult reference ranges. Reply in plain text, "
        "no markdown, no disclaimers, at most 50 words.\n\n"
        f"Age: {_age(patient['date_of_birth'])} years\n"
        f"Glucose: {patient['glucose']:g} mg/dL (fasting status unknown)\n"
        f"Haemoglobin: {patient['haemoglobin']:g} g/dL\n"
        f"Total cholesterol: {patient['cholesterol']:g} mg/dL"
    )


def get_remarks(patient):
    """Return the AI's remark for a patient dict, or raise AIServiceError."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceError("GEMINI_API_KEY is not set. Add it to the .env file and restart the app.")

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    try:
        response = requests.post(
            API_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": build_prompt(patient)}]}]},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise AIServiceError("Could not reach the AI service. Check the internet connection.")

    if response.status_code in (400, 401, 403, 404):
        try:
            reason = response.json()["error"]["message"]
        except (KeyError, ValueError, TypeError):
            reason = "no details given"
        raise AIServiceError(f"The AI service rejected the request (HTTP {response.status_code}): {reason}")
    if response.status_code == 429:
        raise AIServiceError("The AI service rate limit was reached. Wait a minute and retry.")
    if not response.ok:
        raise AIServiceError(f"The AI service returned an error (HTTP {response.status_code}).")

    try:
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError):
        raise AIServiceError("The AI service returned an empty or unreadable answer.")

    text = " ".join(text.replace("*", "").split())
    if not text:
        raise AIServiceError("The AI service returned an empty answer.")
    return text