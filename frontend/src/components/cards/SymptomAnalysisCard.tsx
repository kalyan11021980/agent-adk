import { SeverityBadge } from "@/components/ui/SeverityBadge";
import { SEVERITY_CONFIG } from "@/lib/constants";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Props {
  data: Record<string, any>;
}

export function SymptomAnalysisCard({ data }: Props) {
  const severity = data.severity as keyof typeof SEVERITY_CONFIG ?? "low";
  const symptoms: string[] = Array.isArray(data.reported_symptoms)
    ? data.reported_symptoms
    : [];
  const conditions: Array<{ condition: string; likelihood: string }> =
    Array.isArray(data.possible_conditions) ? data.possible_conditions : [];
  const recommendations: string[] = Array.isArray(data.recommendations)
    ? data.recommendations
    : [];
  const whenToSeekCare = data.when_to_seek_care ?? "";
  const disclaimer = data.disclaimer ?? "";

  return (
    <div className="rounded-lg border border-medical-border bg-white shadow-sm text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-medical-border bg-teal-50/60 px-3 py-2 rounded-t-lg">
        <h3 className="text-sm font-semibold text-teal-800">Symptom Analysis</h3>
        <SeverityBadge severity={severity} />
      </div>

      <div className="space-y-2.5 px-3 py-2.5">
        {symptoms.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold uppercase tracking-wider text-medical-muted">Symptoms:</span>
            {symptoms.map((s, i) => (
              <span key={i} className="rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-700">
                {s}
              </span>
            ))}
          </div>
        )}

        {conditions.length > 0 && (
          <div>
            <p className="mb-1 font-semibold uppercase tracking-wider text-medical-muted">Possible Conditions</p>
            <div className="space-y-1">
              {conditions.map((c, i) => (
                <div key={i} className="flex items-center justify-between rounded border border-medical-border px-2.5 py-1.5">
                  <span className="font-medium text-medical-text">{c.condition}</span>
                  <span className="font-semibold uppercase text-medical-muted">{c.likelihood}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {recommendations.length > 0 && (
          <div>
            <p className="mb-1 font-semibold uppercase tracking-wider text-medical-muted">Recommendations</p>
            <ul className="space-y-0.5">
              {recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-1.5 text-medical-text">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-teal-500" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {whenToSeekCare && (
          <div className="rounded border border-red-200 bg-red-50 px-2.5 py-1.5">
            <p className="font-medium text-red-800">Seek care: {whenToSeekCare}</p>
          </div>
        )}

        {disclaimer && (
          <p className="italic text-medical-muted">{disclaimer}</p>
        )}
      </div>
    </div>
  );
}
