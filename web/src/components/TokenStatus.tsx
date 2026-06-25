"use client";

import { useEffect, useState } from "react";

type Status = { tokensLeft: number | null; refillRate: number | null; error?: string };

export default function TokenStatus() {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch("/api/tokens")
      .then((r) => r.json())
      .then((d) => alive && setStatus(d))
      .catch(() => alive && setStatus({ tokensLeft: null, refillRate: null, error: "недоступно" }))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="card p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Токены Keepa
      </div>
      {loading ? (
        <div className="mt-2 text-sm text-slate-400">Загрузка…</div>
      ) : status?.error ? (
        <div className="mt-2 text-sm text-amber-600">{status.error}</div>
      ) : (
        <div className="mt-1">
          <div className="text-2xl font-semibold text-slate-900">
            {status?.tokensLeft ?? "—"}
          </div>
          <div className="text-xs text-slate-500">
            пополнение {status?.refillRate ?? "—"}/мин
          </div>
        </div>
      )}
    </div>
  );
}
