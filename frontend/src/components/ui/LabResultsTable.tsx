import type { LabResult } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

interface LabResultsTableProps {
  results: LabResult[];
}

export function LabResultsTable({ results }: LabResultsTableProps) {
  if (results.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-medical-border text-left">
            <th className="pb-1 font-semibold text-medical-muted">Test</th>
            <th className="pb-1 font-semibold text-medical-muted">Value</th>
            <th className="pb-1 font-semibold text-medical-muted">Range</th>
            <th className="pb-1 font-semibold text-medical-muted">Status</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className="border-b border-medical-border/50 last:border-0">
              <td className="py-1 font-medium text-medical-text">{r.test_name}</td>
              <td className="py-1 text-medical-muted">{r.value} {r.unit}</td>
              <td className="py-1 text-medical-muted">{r.reference_range}</td>
              <td className="py-1"><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
