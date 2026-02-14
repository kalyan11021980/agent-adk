interface VitalsGridProps {
  vitals: Record<string, string>;
}

export function VitalsGrid({ vitals }: VitalsGridProps) {
  const entries = Object.entries(vitals);
  if (entries.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
      {entries.map(([label, value]) => (
        <div key={label} className="rounded border border-medical-border bg-teal-50/50 px-2 py-1">
          <p className="text-[10px] font-medium text-medical-muted">{label}</p>
          <p className="font-semibold text-medical-text">{value}</p>
        </div>
      ))}
    </div>
  );
}
