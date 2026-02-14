/* ───────────────────── Card schemas (mirrors backend Pydantic models) ───── */

export interface Medication {
  name: string;
  dosage: string;
  frequency: string;
}

export interface VisitSummaryCard {
  component_type: "visit_summary_card";
  visit_date: string;
  provider_name: string;
  provider_specialty: string;
  diagnosis: string[];
  clinical_notes: string;
  medications: Medication[];
  follow_up: string;
  vitals: Record<string, string>;
}

export interface PossibleCondition {
  condition: string;
  likelihood: string;
}

export interface SymptomAnalysisCard {
  component_type: "symptom_analysis_card";
  reported_symptoms: string[];
  possible_conditions: PossibleCondition[];
  severity: "low" | "moderate" | "high" | "urgent";
  recommendations: string[];
  when_to_seek_care: string;
  disclaimer: string;
}

export interface LabResult {
  test_name: string;
  value: string;
  unit: string;
  reference_range: string;
  status: "normal" | "low" | "high" | "critical";
}

export interface LabReportCard {
  component_type: "lab_report_card";
  report_date: string;
  ordering_provider: string;
  results: LabResult[];
  summary: string;
  abnormal_count: number;
  follow_up_needed: boolean;
}

export interface CardError {
  component_type: "error";
  error: true;
  message: string;
}

export type HealthCard =
  | VisitSummaryCard
  | SymptomAnalysisCard
  | LabReportCard
  | CardError;

/* ───────────────────── A2A protocol types (subset we consume) ──────────── */

export interface A2ATextPart {
  kind: "text";
  text: string;
}

export interface A2ADataPart {
  kind: "data";
  data: Record<string, unknown>;
  metadata?: Record<string, string>;
}

export type A2APart = A2ATextPart | A2ADataPart;

export interface A2AMessage {
  role: "user" | "agent" | "ROLE_USER" | "ROLE_AGENT";
  parts?: A2APart[];
  content?: A2APart[];
  messageId?: string;
}

export interface A2ATask {
  id: string;
  status: {
    state: string;
    message?: A2AMessage;
  };
  artifacts?: Array<{
    parts?: A2APart[];
    content?: A2APart[];
  }>;
  history?: A2AMessage[];
}

export interface A2AResponse {
  result?: A2ATask;
  error?: {
    code: number;
    message: string;
  };
}

/* ───────────────────── Chat state types ────────────────────────────────── */

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  card?: HealthCard;
  timestamp: number;
  isLoading?: boolean;
}

export type ChatAction =
  | { type: "ADD_USER_MESSAGE"; text: string }
  | { type: "ADD_AGENT_PLACEHOLDER" }
  | { type: "RESOLVE_AGENT_MESSAGE"; text: string; card?: HealthCard }
  | { type: "REJECT_AGENT_MESSAGE"; error: string };

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
}
