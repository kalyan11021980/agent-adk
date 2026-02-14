import { LabResultsTable } from "@/components/ui/LabResultsTable";
import type { LabResult } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Props {
  data: Record<string, any>;
}

export function LabReportCard({ data }: Props) {
  const reportDate = data.report_date ?? "";
  const orderingProvider = data.ordering_provider ?? "";
  const summary = data.summary ?? "";
  const abnormalCount = Number(data.abnormal_count) || 0;
  const followUpNeeded = Boolean(data.follow_up_needed);
  const results: LabResult[] = Array.isArray(data.results) ? data.results : [];

  return (
    <div className="rounded-lg border border-medical-border bg-white shadow-sm text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-medical-border bg-teal-50/60 px-3 py-2 rounded-t-lg">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-teal-800">Lab Report</h3>
          {orderingProvider && (
            <span className="text-medical-muted">{orderingProvider}</span>
          )}
        </div>
        {reportDate && (
          <span className="rounded-full bg-teal-100 px-2 py-0.5 font-medium text-teal-700">
            {reportDate}
          </span>
        )}
      </div>

      <div className="space-y-2.5 px-3 py-2.5">
        {summary && (
          <p className="leading-relaxed text-medical-text">{summary}</p>
        )}

        {abnormalCount > 0 && (
          <div className="rounded border border-orange-200 bg-orange-50 px-2.5 py-1.5">
            <p className="font-medium text-orange-800">
              {abnormalCount} abnormal result{abnormalCount > 1 ? "s" : ""} detected
            </p>
          </div>
        )}

        {results.length > 0 && <LabResultsTable results={results} />}

        <div
          className={`rounded border px-2.5 py-1.5 ${
            followUpNeeded
              ? "border-amber-200 bg-amber-50"
              : "border-green-200 bg-green-50"
          }`}
        >
          <p className={`font-medium ${followUpNeeded ? "text-amber-800" : "text-green-800"}`}>
            {followUpNeeded
              ? "Follow-up recommended — please schedule an appointment."
              : "No immediate follow-up needed."}
          </p>
        </div>
      </div>
    </div>
  );
}
