import type { Medication } from "@/lib/types";

interface MedicationTableProps {
  medications: Medication[];
}

export function MedicationTable({ medications }: MedicationTableProps) {
  if (medications.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-medical-border text-left">
            <th className="pb-1 font-semibold text-medical-muted">Medication</th>
            <th className="pb-1 font-semibold text-medical-muted">Dosage</th>
            <th className="pb-1 font-semibold text-medical-muted">Frequency</th>
          </tr>
        </thead>
        <tbody>
          {medications.map((med, i) => (
            <tr key={i} className="border-b border-medical-border/50 last:border-0">
              <td className="py-1 font-medium text-medical-text">{med.name}</td>
              <td className="py-1 text-medical-muted">{med.dosage}</td>
              <td className="py-1 text-medical-muted">{med.frequency}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
