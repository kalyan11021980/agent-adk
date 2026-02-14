"""Tool for retrieving patient visit summaries.

Replace the mock implementation with real EHR/API calls when ready.
The function signature and return shape should stay the same.
"""

from __future__ import annotations

# Mock data store — swap with database or API client in production.
_MOCK_VISITS: dict[str, dict] = {
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


def get_visit_summary(patient_id: str) -> dict:
    """Retrieve the most recent visit summary for a patient.

    Use this tool when the user asks for a visit summary, appointment
    details, or clinical records for a specific patient ID.

    Args:
        patient_id: The unique patient identifier (e.g. 'P001').

    Returns:
        A dictionary indicating the outcome.
        On success, status is 'success' and includes visit details such as
        provider info, diagnosis, medications, clinical notes, vitals, and
        follow-up instructions.
        On error, status is 'error' and includes an 'error_message'.
        Example success: {'status': 'success', 'component_type': 'visit_summary_card', 'provider_name': 'Dr. Sarah Chen', ...}
        Example error: {'status': 'error', 'error_message': 'No visit records found for patient ...'}
    """
    visit = _MOCK_VISITS.get(patient_id)
    if visit is None:
        return {
            "status": "error",
            "error_message": (
                f"No visit records found for patient '{patient_id}'. "
                "Available demo IDs: P001, P002."
            ),
        }
    return {"status": "success", "component_type": "visit_summary_card", **visit}
