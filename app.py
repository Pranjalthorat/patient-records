"""Patient blood test records: Flask routes."""
import os
import secrets
from datetime import date

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

import ai_client
import database
from validation import BLOOD_FIELDS, validate_patient

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

# The fields that feed the AI prediction. If none of them change during an edit,
# the saved remarks are still correct and the API is not called again.
PREDICTION_FIELDS = ("date_of_birth", "glucose", "haemoglobin", "cholesterol")


@app.template_filter("dmy")
def to_dmy(iso_date):
    """2001-11-30 -> 30/11/2001"""
    return date.fromisoformat(iso_date).strftime("%d/%m/%Y")


@app.template_filter("num")
def format_number(value):
    return f"{value:g}"


def run_prediction(patient_id):
    """Ask the AI service for remarks and save them. Flash a warning if that fails."""
    patient = database.get_patient(patient_id)
    try:
        remarks = ai_client.get_remarks(patient)
    except ai_client.AIServiceError as error:
        flash(f"Record saved, but the AI prediction failed: {error}", "warning")
        return False
    database.set_remarks(patient_id, remarks)
    return True


def check_duplicates(clean, errors, exclude_id=None):
    """Add an error if the email, or the name + date of birth, is already on file."""
    if "email" in clean and database.email_exists(clean["email"], exclude_id):
        errors["email"] = "Another patient already uses this email address."
    if "full_name" in clean and "date_of_birth" in clean and database.person_exists(
        clean["full_name"], clean["date_of_birth"], exclude_id
    ):
        errors["full_name"] = "A patient with this name and date of birth already exists."


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    patients = database.list_patients(search)
    return render_template("list.html", patients=patients, search=search)


@app.route("/patients/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template("form.html", mode="create", form={}, errors={}, fields=BLOOD_FIELDS)

    clean, errors = validate_patient(request.form)
    check_duplicates(clean, errors)
    if errors:
        return render_template("form.html", mode="create", form=request.form, errors=errors, fields=BLOOD_FIELDS), 400

    patient_id = database.insert_patient(clean)
    if run_prediction(patient_id):
        flash(f"{clean['full_name']} was added and the AI remarks were generated.", "success")
    return redirect(url_for("index"))


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
def edit(patient_id):
    patient = database.get_patient(patient_id)
    if patient is None:
        abort(404)

    if request.method == "GET":
        form = {
            "full_name": patient["full_name"],
            "date_of_birth": to_dmy(patient["date_of_birth"]),
            "email": patient["email"],
            "glucose": format_number(patient["glucose"]),
            "haemoglobin": format_number(patient["haemoglobin"]),
            "cholesterol": format_number(patient["cholesterol"]),
        }
        return render_template("form.html", mode="edit", patient=patient, form=form, errors={}, fields=BLOOD_FIELDS)

    clean, errors = validate_patient(request.form)
    check_duplicates(clean, errors, exclude_id=patient_id)
    if errors:
        return render_template("form.html", mode="edit", patient=patient, form=request.form, errors=errors, fields=BLOOD_FIELDS), 400

    needs_new_prediction = patient["remarks"] is None or any(
        clean[field] != patient[field] for field in PREDICTION_FIELDS
    )
    database.update_patient(patient_id, clean)
    if needs_new_prediction:
        database.set_remarks(patient_id, None)  # old remarks no longer match the values
        if run_prediction(patient_id):
            flash(f"{clean['full_name']} was updated and the AI remarks were refreshed.", "success")
    else:
        flash(f"{clean['full_name']} was updated.", "success")
    return redirect(url_for("index"))


@app.route("/patients/<int:patient_id>/predict", methods=["POST"])
def retry_prediction(patient_id):
    if database.get_patient(patient_id) is None:
        abort(404)
    if run_prediction(patient_id):
        flash("AI remarks generated.", "success")
    return redirect(url_for("index"))


@app.route("/patients/<int:patient_id>/delete", methods=["GET", "POST"])
def delete(patient_id):
    patient = database.get_patient(patient_id)
    if patient is None:
        abort(404)
    if request.method == "POST":
        database.delete_patient(patient_id)
        flash(f"{patient['full_name']} was deleted.", "success")
        return redirect(url_for("index"))
    return render_template("confirm_delete.html", patient=patient)


@app.errorhandler(404)
def not_found(_error):
    return render_template("not_found.html"), 404


database.init_db()

if __name__ == "__main__":
    app.run(debug=True)
