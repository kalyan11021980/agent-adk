"""In-memory repository implementations.

These serve as the default data source for development and demos.
Replace with database-backed or API-backed implementations for production
by swapping the repository bindings in the dependency container.
"""

from __future__ import annotations

from health_ai_medgemma.repositories.base import (
    LabReportRepository,
    SymptomRepository,
    VisitRepository,
)

# ---------------------------------------------------------------------------
# Visit data
# ---------------------------------------------------------------------------

_VISITS: dict[str, dict] = {
    "P001": {
        "visit_date": "2025-12-15",
        "provider_name": "Dr. Sarah Chen",
        "provider_specialty": "Internal Medicine",
        "diagnosis": ["Upper Respiratory Infection", "Mild Dehydration"],
        "clinical_notes": (
            "Patient presented with 3-day history of cough, sore throat, "
            "and low-grade fever. Lungs clear on auscultation. No signs of "
            "pneumonia. Advised rest and hydration."
        ),
        "medications": [
            {"name": "Amoxicillin", "dosage": "500mg", "frequency": "3x daily for 7 days"},
            {"name": "Ibuprofen", "dosage": "400mg", "frequency": "As needed for fever"},
        ],
        "follow_up": "Return in 7 days if symptoms persist or worsen.",
        "vitals": {
            "blood_pressure": "120/78 mmHg",
            "heart_rate": "82 bpm",
            "temperature": "100.2 F",
            "oxygen_saturation": "97%",
        },
    },
    "P002": {
        "visit_date": "2026-01-20",
        "provider_name": "Dr. Michael Roberts",
        "provider_specialty": "Cardiology",
        "diagnosis": ["Hypertension — Stage 1"],
        "clinical_notes": (
            "Routine follow-up for elevated blood pressure noted during annual "
            "physical. Patient asymptomatic. Lifestyle modifications discussed. "
            "Started on low-dose antihypertensive."
        ),
        "medications": [
            {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily"},
        ],
        "follow_up": "Recheck blood pressure in 4 weeks. Lab work for renal function.",
        "vitals": {
            "blood_pressure": "142/90 mmHg",
            "heart_rate": "76 bpm",
            "temperature": "98.6 F",
            "oxygen_saturation": "99%",
        },
    },
}


class InMemoryVisitRepository(VisitRepository):

    def __init__(self, data: dict[str, dict] | None = None) -> None:
        self._data = data if data is not None else _VISITS

    async def get_visit_summary(self, patient_id: str) -> dict | None:
        return self._data.get(patient_id)

    async def list_patient_ids(self) -> list[str]:
        return list(self._data.keys())


# ---------------------------------------------------------------------------
# Symptom data
# ---------------------------------------------------------------------------

_SYMPTOM_DB: dict[str, dict] = {
    "cough": {
        "conditions": [
            {"condition": "Common Cold", "likelihood": "high"},
            {"condition": "Allergies", "likelihood": "moderate"},
            {"condition": "Bronchitis", "likelihood": "low"},
        ],
        "severity": "low",
        "recommendations": [
            "Stay hydrated and rest",
            "Use honey and warm liquids to soothe throat",
            "Consider over-the-counter cough suppressant",
        ],
        "when_to_seek_care": (
            "Seek medical attention if cough persists beyond 2 weeks, "
            "produces blood-tinged sputum, or is accompanied by high fever "
            "or difficulty breathing."
        ),
    },
    "headache": {
        "conditions": [
            {"condition": "Tension Headache", "likelihood": "high"},
            {"condition": "Migraine", "likelihood": "moderate"},
            {"condition": "Dehydration", "likelihood": "moderate"},
        ],
        "severity": "low",
        "recommendations": [
            "Rest in a quiet, dark room",
            "Take over-the-counter pain relievers (acetaminophen or ibuprofen)",
            "Stay hydrated — drink plenty of water",
        ],
        "when_to_seek_care": (
            "Seek immediate care if headache is sudden and severe, "
            "accompanied by confusion, vision changes, stiff neck, or fever."
        ),
    },
    "chest pain": {
        "conditions": [
            {"condition": "Musculoskeletal Strain", "likelihood": "moderate"},
            {"condition": "Acid Reflux (GERD)", "likelihood": "moderate"},
            {"condition": "Angina / Cardiac Event", "likelihood": "low"},
        ],
        "severity": "high",
        "recommendations": [
            "Stop physical activity and rest",
            "Do NOT ignore chest pain — treat it seriously",
            "If pain is severe or accompanied by shortness of breath, call emergency services",
        ],
        "when_to_seek_care": (
            "Call emergency services immediately if chest pain is crushing, "
            "radiates to arm/jaw, or is accompanied by shortness of breath, "
            "sweating, or nausea."
        ),
    },
    "fever": {
        "conditions": [
            {"condition": "Viral Infection", "likelihood": "high"},
            {"condition": "Bacterial Infection", "likelihood": "moderate"},
            {"condition": "Inflammatory Condition", "likelihood": "low"},
        ],
        "severity": "moderate",
        "recommendations": [
            "Rest and stay hydrated",
            "Take acetaminophen or ibuprofen to reduce fever",
            "Monitor temperature regularly",
        ],
        "when_to_seek_care": (
            "Seek medical attention if fever exceeds 103F (39.4C), "
            "lasts more than 3 days, or is accompanied by severe headache, "
            "rash, or stiff neck."
        ),
    },
}

_DEFAULT_ANALYSIS: dict = {
    "conditions": [
        {"condition": "Requires further evaluation", "likelihood": "unknown"},
    ],
    "severity": "moderate",
    "recommendations": [
        "Monitor your symptoms closely",
        "Keep a symptom diary noting onset, duration, and triggers",
        "Schedule an appointment with your primary care provider",
    ],
    "when_to_seek_care": (
        "Seek medical attention if symptoms worsen, persist beyond a few days, "
        "or significantly interfere with daily activities."
    ),
}


class InMemorySymptomRepository(SymptomRepository):

    def __init__(
        self,
        data: dict[str, dict] | None = None,
        default: dict | None = None,
    ) -> None:
        self._data = data if data is not None else _SYMPTOM_DB
        self._default = default if default is not None else _DEFAULT_ANALYSIS

    async def lookup_symptoms(self, keywords: list[str]) -> list[dict]:
        results: list[dict] = []
        for kw in keywords:
            entry = self._data.get(kw.lower())
            if entry:
                results.append({"keyword": kw, **entry})
        return results

    async def get_default_analysis(self) -> dict:
        return dict(self._default)


# ---------------------------------------------------------------------------
# Lab report data
# ---------------------------------------------------------------------------

_LAB_REPORTS: dict[str, dict] = {
    "P001": {
        "report_date": "2026-02-10",
        "ordering_provider": "Dr. Sarah Chen",
        "results": [
            {
                "test_name": "White Blood Cell Count (WBC)",
                "value": "11.2",
                "unit": "x10^3/uL",
                "reference_range": "4.5-11.0",
                "status": "high",
            },
            {
                "test_name": "Red Blood Cell Count (RBC)",
                "value": "4.8",
                "unit": "x10^6/uL",
                "reference_range": "4.5-5.5",
                "status": "normal",
            },
            {
                "test_name": "Hemoglobin (Hgb)",
                "value": "14.2",
                "unit": "g/dL",
                "reference_range": "13.5-17.5",
                "status": "normal",
            },
            {
                "test_name": "Hematocrit (Hct)",
                "value": "42.1",
                "unit": "%",
                "reference_range": "38.0-50.0",
                "status": "normal",
            },
            {
                "test_name": "Platelet Count",
                "value": "245",
                "unit": "x10^3/uL",
                "reference_range": "150-400",
                "status": "normal",
            },
            {
                "test_name": "Glucose (Fasting)",
                "value": "108",
                "unit": "mg/dL",
                "reference_range": "70-100",
                "status": "high",
            },
            {
                "test_name": "Creatinine",
                "value": "0.9",
                "unit": "mg/dL",
                "reference_range": "0.7-1.3",
                "status": "normal",
            },
        ],
    },
    "P002": {
        "report_date": "2026-01-25",
        "ordering_provider": "Dr. Michael Roberts",
        "results": [
            {
                "test_name": "Total Cholesterol",
                "value": "215",
                "unit": "mg/dL",
                "reference_range": "<200",
                "status": "high",
            },
            {
                "test_name": "LDL Cholesterol",
                "value": "142",
                "unit": "mg/dL",
                "reference_range": "<100",
                "status": "high",
            },
            {
                "test_name": "HDL Cholesterol",
                "value": "48",
                "unit": "mg/dL",
                "reference_range": ">40",
                "status": "normal",
            },
            {
                "test_name": "Triglycerides",
                "value": "160",
                "unit": "mg/dL",
                "reference_range": "<150",
                "status": "high",
            },
        ],
    },
}


def _build_lab_report(data: dict) -> dict:
    """Add computed summary fields to raw lab data."""
    results = data["results"]
    abnormal = [r for r in results if r["status"] != "normal"]

    summary_parts: list[str] = []
    if abnormal:
        flags = ", ".join(r["test_name"] for r in abnormal)
        summary_parts.append(f"Abnormal values detected: {flags}.")
    else:
        summary_parts.append("All values are within normal reference ranges.")

    return {
        **data,
        "summary": " ".join(summary_parts),
        "abnormal_count": len(abnormal),
        "follow_up_needed": len(abnormal) > 0,
    }


class InMemoryLabReportRepository(LabReportRepository):

    def __init__(self, data: dict[str, dict] | None = None) -> None:
        self._data = data if data is not None else _LAB_REPORTS

    async def get_lab_report(self, patient_id: str) -> dict | None:
        raw = self._data.get(patient_id)
        if raw is None:
            return None
        return _build_lab_report(raw)

    async def list_patient_ids(self) -> list[str]:
        return list(self._data.keys())
