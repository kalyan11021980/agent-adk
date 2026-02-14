import { STATUS_CONFIG } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: keyof typeof STATUS_CONFIG;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.normal;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
        config.bg,
        config.text,
        className
      )}
    >
      {config.label}
    </span>
  );
}
