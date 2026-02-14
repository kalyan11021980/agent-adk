import { VitalsGrid } from "@/components/ui/VitalsGrid";
import { MedicationTable } from "@/components/ui/MedicationTable";
import type { Medication } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Props {
  data: Record<string, any>;
}

export function VisitSummaryCard({ data }: Props) {
  const providerName = data.provider_name ?? "";
  const providerSpecialty = data.provider_specialty ?? "";
  const visitDate = data.visit_date ?? "";
  const clinicalNotes = data.clinical_notes ?? "";
  const followUp = data.follow_up ?? data.follow_up_instructions ?? "";

  const diagnosis: string[] = Array.isArray(data.diagnosis)
    ? data.diagnosis
    : typeof data.diagnosis === "string"
      ? data.diagnosis.split(",").map((s: string) => s.trim())
      : [];

  const medications: Medication[] = Array.isArray(data.medications)
    ? data.medications
    : [];

  const rawVitals = data.vitals ?? {};
  const vitals: Record<string, string> = {};
  for (const [k, v] of Object.entries(rawVitals)) {
    vitals[k] = String(v);
  }

  return (
    <div className="rounded-lg border border-medical-border bg-white shadow-sm text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-medical-border bg-teal-50/60 px-3 py-2 rounded-t-lg">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-teal-800">Visit Summary</h3>
          {providerName && (
            <span className="text-medical-muted">
              {providerName}{providerSpecialty ? ` · ${providerSpecialty}` : ""}
            </span>
          )}
        </div>
        {visitDate && (
          <span className="rounded-full bg-teal-100 px-2 py-0.5 font-medium text-teal-700">
            {visitDate}
          </span>
        )}
      </div>

      <div className="space-y-2.5 px-3 py-2.5">
        {diagnosis.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold uppercase tracking-wider text-medical-muted">Dx:</span>
            {diagnosis.map((d, i) => (
              <span key={i} className="rounded-full bg-teal-100 px-2 py-0.5 font-medium text-teal-800">
                {d}
              </span>
            ))}
          </div>
        )}

        {clinicalNotes && (
          <p className="leading-relaxed text-medical-text">{clinicalNotes}</p>
        )}

        {Object.keys(vitals).length > 0 && <VitalsGrid vitals={vitals} />}

        {medications.length > 0 && <MedicationTable medications={medications} />}

        {followUp && (
          <div className="rounded border border-teal-200 bg-teal-50 px-2.5 py-1.5">
            <p className="font-medium text-teal-800">Follow-up: {followUp}</p>
          </div>
        )}
      </div>
    </div>
  );
}
