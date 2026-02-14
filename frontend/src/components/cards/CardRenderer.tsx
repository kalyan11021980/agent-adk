import type { HealthCard } from "@/lib/types";
import { VisitSummaryCard } from "./VisitSummaryCard";
import { SymptomAnalysisCard } from "./SymptomAnalysisCard";
import { LabReportCard } from "./LabReportCard";
import { ErrorCard } from "./ErrorCard";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Props {
  card: HealthCard;
}

export function CardRenderer({ card }: Props) {
  const data = card as Record<string, any>;

  switch (card.component_type) {
    case "visit_summary_card":
      return <VisitSummaryCard data={data} />;
    case "symptom_analysis_card":
      return <SymptomAnalysisCard data={data} />;
    case "lab_report_card":
      return <LabReportCard data={data} />;
    case "error":
      return <ErrorCard data={card} />;
    default:
      return (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
          Unknown card type:{" "}
          <code>{(card as { component_type: string }).component_type}</code>
        </div>
      );
  }
}
