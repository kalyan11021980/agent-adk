"""Tool for analyzing reported symptoms.

Replace the mock implementation with a real clinical decision-support
API when ready. The function signature and return shape should stay the same.
"""

from __future__ import annotations

_DISCLAIMER = (
    "This is not a medical diagnosis. The information provided is for "
    "educational purposes only. Always consult a qualified healthcare "
    "professional for medical advice, diagnosis, or treatment."
)

# Simple keyword-based mock — a real implementation would call a clinical API.
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

_DEFAULT_ANALYSIS = {
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


def analyze_symptoms(symptoms: str) -> dict:
    """Analyze reported symptoms and provide health guidance.

    Use this tool when the user describes symptoms they are experiencing,
    such as cough, headache, fever, chest pain, or any health complaints.

    Args:
        symptoms: A free-text description of the patient's symptoms
                  (e.g. 'I have been coughing and have a fever').

    Returns:
        A dictionary indicating the outcome.
        On success, status is 'success' and includes possible conditions,
        severity level, recommendations, and when to seek care.
        Example success: {'status': 'success', 'component_type': 'symptom_analysis_card', 'severity': 'low', ...}
    """
    symptoms_lower = symptoms.lower()
    matched_symptoms: list[str] = []
    all_conditions: list[dict[str, str]] = []
    max_severity = "low"
    all_recommendations: list[str] = []
    when_to_seek: list[str] = []

    severity_rank = {"low": 0, "moderate": 1, "high": 2, "urgent": 3}

    for keyword, data in _SYMPTOM_DB.items():
        if keyword in symptoms_lower:
            matched_symptoms.append(keyword)
            all_conditions.extend(data["conditions"])
            if severity_rank.get(data["severity"], 0) > severity_rank.get(max_severity, 0):
                max_severity = data["severity"]
            all_recommendations.extend(data["recommendations"])
            when_to_seek.append(data["when_to_seek_care"])

    if not matched_symptoms:
        matched_symptoms = [symptoms.strip()]
        all_conditions = _DEFAULT_ANALYSIS["conditions"]
        max_severity = _DEFAULT_ANALYSIS["severity"]
        all_recommendations = _DEFAULT_ANALYSIS["recommendations"]
        when_to_seek = [_DEFAULT_ANALYSIS["when_to_seek_care"]]

    # Deduplicate recommendations while preserving order.
    seen: set[str] = set()
    unique_recs: list[str] = []
    for rec in all_recommendations:
        if rec not in seen:
            seen.add(rec)
            unique_recs.append(rec)

    return {
        "status": "success",
        "component_type": "symptom_analysis_card",
        "reported_symptoms": matched_symptoms,
        "possible_conditions": all_conditions,
        "severity": max_severity,
        "recommendations": unique_recs,
        "when_to_seek_care": " ".join(when_to_seek),
        "disclaimer": _DISCLAIMER,
    }
