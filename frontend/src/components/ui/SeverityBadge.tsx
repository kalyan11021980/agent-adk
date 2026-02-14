import { SEVERITY_CONFIG } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface SeverityBadgeProps {
  severity: keyof typeof SEVERITY_CONFIG;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.low;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold",
        config.bg,
        config.text,
        className
      )}
    >
      {config.label}
    </span>
  );
}
