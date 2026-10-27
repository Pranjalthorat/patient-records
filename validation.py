"""Input validation for the patient form."""
import math
import re
from datetime import date

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
DATE_RE = re.compile(r"(\d{2})[/.-](\d{2})[/.-](\d{4})")

# field -> (label, minimum, maximum, unit). Values outside the range are almost
# certainly typing mistakes, so they are rejected rather than sent to the AI.
BLOOD_FIELDS = {
    "glucose": ("Glucose", 20, 600, "mg/dL"),
    "haemoglobin": ("Haemoglobin", 3, 25, "g/dL"),
    "cholesterol": ("Cholesterol", 50, 600, "mg/dL"),
}


def parse_dob(text):
    """Turn dd/mm/yyyy text into a date. Returns (date, error_message)."""
    match = DATE_RE.fullmatch(text)
    if not match:
        return None, "Enter the date as dd/mm/yyyy."
    day, month, year = (int(part) for part in match.groups())
    try:
        dob = date(year, month, day)
    except ValueError:
        return None, f"{text} is not a real calendar date."
    today = date.today()
    if dob > today:
        return None, "Date of birth cannot be in the future."
    if dob.year < today.year - 120:
        return None, "Date of birth is too far in the past."
    return dob, None


def validate_patient(form):
    """Check the submitted form. Returns (clean_data, errors); errors maps field -> message."""
    errors = {}
    clean = {}

    name = " ".join(form.get("full_name", "").split())
    if len(name) < 2:
        errors["full_name"] = "Enter the patient's full name."
    elif not all(ch.isalpha() or ch in " .'-" for ch in name):
        errors["full_name"] = "Names can only contain letters, spaces, hyphens, apostrophes and full stops."
    else:
        clean["full_name"] = name

    dob_text = form.get("date_of_birth", "").strip()
    if not dob_text:
        errors["date_of_birth"] = "Enter the date of birth."
    else:
        dob, problem = parse_dob(dob_text)
        if problem:
            errors["date_of_birth"] = problem
        else:
            clean["date_of_birth"] = dob.isoformat()

    email = form.get("email", "").strip()
    if not email:
        errors["email"] = "Enter an email address."
    elif not EMAIL_RE.fullmatch(email):
        errors["email"] = "Enter a valid email address, for example name@example.com."
    else:
        clean["email"] = email

    for field, (label, low, high, unit) in BLOOD_FIELDS.items():
        text = form.get(field, "").strip()
        if not text:
            errors[field] = f"Enter the {label.lower()} value."
            continue
        try:
            value = float(text)
        except ValueError:
            errors[field] = f"{label} must be a number."
            continue
        if not math.isfinite(value):
            errors[field] = f"{label} must be a number."
        elif not low <= value <= high:
            errors[field] = f"{label} must be between {low} and {high} {unit}."
        else:
            clean[field] = value

    return clean, errors
