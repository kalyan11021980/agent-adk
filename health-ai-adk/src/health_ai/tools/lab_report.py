"""Tool for summarizing lab report results.

Replace the mock implementation with real lab system integration
when ready. The function signature and return shape should stay the same.
"""

from __future__ import annotations


def summarize_lab_report(report_text: str) -> dict:
    """Parse and summarize laboratory test results.

    Use this tool when the user asks about lab results, blood work, or
    any laboratory report. Pass the user's request text as report_text.

    Args:
        report_text: Raw lab report text or a report identifier. In this
                     mock implementation, any input returns a sample
                     Complete Blood Count (CBC) report.

    Returns:
        A dictionary indicating the outcome.
        On success, status is 'success' and includes structured lab results
        with reference ranges, status flags, a summary, and follow-up guidance.
        Example success: {'status': 'success', 'component_type': 'lab_report_card', 'results': [...], ...}
    """
    # Mock CBC results — a real implementation would parse the report_text
    # or call a lab information system API.
    results = [
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
    ]

    abnormal = [r for r in results if r["status"] != "normal"]

    summary_parts = []
    if abnormal:
        flags = ", ".join(r["test_name"] for r in abnormal)
        summary_parts.append(f"Abnormal values detected: {flags}.")
        summary_parts.append(
            "Slightly elevated WBC may indicate a mild infection or "
            "inflammatory response. Elevated fasting glucose suggests "
            "pre-diabetic range — lifestyle modifications and repeat "
            "testing recommended."
        )
    else:
        summary_parts.append("All values are within normal reference ranges.")

    return {
        "status": "success",
        "component_type": "lab_report_card",
        "report_date": "2026-02-10",
        "ordering_provider": "Dr. Sarah Chen",
        "results": results,
        "summary": " ".join(summary_parts),
        "abnormal_count": len(abnormal),
        "follow_up_needed": len(abnormal) > 0,
    }
