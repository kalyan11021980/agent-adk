import type { CardError } from "@/lib/types";

interface Props {
  data: CardError;
}

export function ErrorCard({ data }: Props) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 shadow-sm">
      <div className="flex items-start gap-2 text-xs">
        <span className="text-sm">&#9888;</span>
        <div>
          <p className="font-semibold text-red-800">Error</p>
          <p className="text-red-700">{data.message}</p>
        </div>
      </div>
    </div>
  );
}
