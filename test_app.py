"""Runs the 10 assignment records through the app with the AI call replaced by a stub."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ai_client
import app as app_module
import database

# (test number, name, dob, email, glucose, haemoglobin, cholesterol, expected fields with errors)
CASES = [
    (1, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180", set()),
    (2, "John Hunter", "10.12.1990", "hunter@gmail", "94", "15", "200", {"email"}),
    (3, "Darryl Tim", "12.11.1993", "timd@smh.com.au", "240", "18.6", "326", set()),
    (4, "Peter Larry", "31.11.2001", "Larry@hotmail.com", "88", "11.5", "165", {"date_of_birth"}),
    (5, "Sam Kerr", "09.12.2006", "sam@news.com.au", "198", "8.9", "192", set()),
    (6, "Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180", {"email", "full_name"}),
    (7, "Madison XI", "12.09.1998", "madison@hotmail.com", "85", "7.6", "163", set()),
    (8, "Kris Wu", "19.10.2030", "Kris.wu.gmail.com", "79", "16.5", "197", {"date_of_birth", "email"}),
    (9, "Tenille Singh", "30.11.1991", "Tenille@yahoo.com", "101", "15", "310", set()),
    (10, "Prem Kumar", "28.04.1990", "prem@telstra.com", "155", "12.5", "265", set()),
]


def form_data(case):
    _, name, dob, email, glucose, hb, chol, _ = case
    return {"full_name": name, "date_of_birth": dob, "email": email,
            "glucose": glucose, "haemoglobin": hb, "cholesterol": chol}


class PatientRecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(database, "DB_PATH", Path(self.tmp.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        database.init_db()
        self.client = app_module.app.test_client()
        self.ai = mock.patch.object(ai_client, "get_remarks", return_value="Stub remark.")
        self.ai.start()
        self.addCleanup(self.ai.stop)

    def add_all(self):
        outcomes = {}
        for case in CASES:
            response = self.client.post("/patients/new", data=form_data(case))
            outcomes[case[0]] = response
        return outcomes

    def test_assignment_records(self):
        outcomes = self.add_all()
        for case in CASES:
            number, expected = case[0], case[-1]
            response = outcomes[number]
            if expected:
                self.assertEqual(response.status_code, 400, f"test {number} should be rejected")
                page = response.get_data(as_text=True)
                self.assertEqual(page.count('class="invalid"'), len(expected), f"test {number}")
            else:
                self.assertEqual(response.status_code, 302, f"test {number} should be saved")
        names = [p["full_name"] for p in database.list_patients()]
        self.assertEqual(names, ["Robyn Pears", "Darryl Tim", "Sam Kerr", "Madison XI", "Tenille Singh", "Prem Kumar"])

    def test_edit_email_keeps_remarks_without_new_ai_call(self):
        self.add_all()
        self.ai.stop()
        with mock.patch.object(ai_client, "get_remarks") as fake:
            data = form_data(CASES[0])
            data["email"] = "gokul@infocare.com"
            self.assertEqual(self.client.post("/patients/1/edit", data=data).status_code, 302)
            fake.assert_not_called()
        self.ai.start()
        patient = database.get_patient(1)
        self.assertEqual(patient["email"], "gokul@infocare.com")
        self.assertEqual(patient["remarks"], "Stub remark.")

    def test_edit_blood_value_regenerates_remarks(self):
        self.add_all()
        data = form_data(CASES[0])
        data["glucose"] = "100"
        self.client.post("/patients/1/edit", data=data)
        self.assertEqual(database.get_patient(1)["glucose"], 100)

    def test_delete(self):
        self.add_all()
        self.assertEqual(self.client.get("/patients/3/delete").status_code, 200)
        self.assertEqual(self.client.post("/patients/3/delete").status_code, 302)
        self.assertIsNone(database.get_patient(3))
        self.assertEqual(len(database.list_patients()), 5)

    def test_ai_failure_saves_record_and_allows_retry(self):
        self.ai.stop()
        with mock.patch.object(ai_client, "get_remarks", side_effect=ai_client.AIServiceError("down")):
            self.client.post("/patients/new", data=form_data(CASES[0]))
        self.assertIsNone(database.get_patient(1)["remarks"])
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("Prediction pending", page)
        with mock.patch.object(ai_client, "get_remarks", return_value="Recovered."):
            self.client.post("/patients/1/predict")
        self.assertEqual(database.get_patient(1)["remarks"], "Recovered.")
        self.ai.start()

    def test_missing_api_key_message(self):
        self.ai.stop()
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            with self.assertRaises(ai_client.AIServiceError) as ctx:
                ai_client.get_remarks({"date_of_birth": "1990-01-01", "glucose": 1, "haemoglobin": 1, "cholesterol": 1})
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        self.ai.start()


if __name__ == "__main__":
    unittest.main()
