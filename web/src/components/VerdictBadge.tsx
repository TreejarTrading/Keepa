import { verdictClass } from "@/lib/format";

export default function VerdictBadge({ verdict }: { verdict?: string | null }) {
  if (!verdict) return <span className="badge-neutral">—</span>;
  return <span className={verdictClass(verdict)}>{verdict}</span>;
}
