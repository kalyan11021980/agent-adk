export const SEVERITY_CONFIG = {
  low: { label: "Low", bg: "bg-green-100", text: "text-green-800", border: "border-green-300" },
  moderate: { label: "Moderate", bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300" },
  high: { label: "High", bg: "bg-orange-100", text: "text-orange-800", border: "border-orange-300" },
  urgent: { label: "Urgent", bg: "bg-red-100", text: "text-red-800", border: "border-red-300" },
} as const;

export const STATUS_CONFIG = {
  normal: { label: "Normal", bg: "bg-green-100", text: "text-green-800" },
  low: { label: "Low", bg: "bg-yellow-100", text: "text-yellow-800" },
  high: { label: "High", bg: "bg-orange-100", text: "text-orange-800" },
  critical: { label: "Critical", bg: "bg-red-100", text: "text-red-800" },
} as const;

export const KNOWN_COMPONENT_TYPES = [
  "visit_summary_card",
  "symptom_analysis_card",
  "lab_report_card",
  // LLM sometimes drops the _card suffix
  "visit_summary",
  "symptom_analysis",
  "lab_report",
] as const;

/** Normalize component_type to the canonical _card form. */
export function normalizeComponentType(type: string): string {
  const map: Record<string, string> = {
    visit_summary: "visit_summary_card",
    symptom_analysis: "symptom_analysis_card",
    lab_report: "lab_report_card",
  };
  return map[type] ?? type;
}
