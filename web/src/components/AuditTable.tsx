"use client";

import { useState } from "react";
import { dateTime } from "@/lib/format";

type Entry = {
  id: string;
  createdAt: string | Date;
  action: string;
  userEmail: string | null;
  targetType: string | null;
  targetId: string | null;
  ip: string | null;
  detail: unknown;
};

const ACTION_LABELS: Record<string, string> = {
  LOGIN: "Вход", LOGIN_FAILED: "Неудачный вход", LOGOUT: "Выход",
  PASSWORD_CHANGE: "Смена пароля", USER_CREATE: "Создан пользователь",
  USER_UPDATE: "Изменён пользователь", USER_DEACTIVATE: "Отключён пользователь",
  USER_PASSWORD_RESET: "Сброс пароля", SEARCH_RUN: "Поиск", REPORT_CREATE: "Создан отчёт",
  REPORT_VIEW: "Просмотр отчёта", REPORT_DELETE: "Удалён отчёт", VERDICT_OVERRIDE: "Изменён вердикт",
  SAVED_QUERY_CREATE: "Сохранён поиск", SAVED_QUERY_DELETE: "Удалён сохранённый поиск",
};

export default function AuditTable({
  initialEntries, actions,
}: {
  initialEntries: Entry[];
  actions: string[];
}) {
  const [entries, setEntries] = useState<Entry[]>(initialEntries);
  const [action, setAction] = useState("");
  const [user, setUser] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (action) p.set("action", action);
      if (user) p.set("user", user);
      const res = await fetch(`/api/audit?${p.toString()}`);
      const data = await res.json();
      if (res.ok) setEntries(data.entries);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card grid grid-cols-1 gap-3 p-3 md:grid-cols-4">
        <div>
          <label className="label">Действие</label>
          <select className="input" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">Все</option>
            {actions.map((a) => <option key={a} value={a}>{ACTION_LABELS[a] || a}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Пользователь (email)</label>
          <input className="input" value={user} onChange={(e) => setUser(e.target.value)} />
        </div>
        <div className="flex items-end">
          <button className="btn-primary" onClick={load} disabled={loading}>
            {loading ? "Загрузка…" : "Применить"}
          </button>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="th">Время</th>
              <th className="th">Действие</th>
              <th className="th">Пользователь</th>
              <th className="th">Объект</th>
              <th className="th">IP</th>
              <th className="th">Детали</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr><td className="td py-8 text-center text-slate-500" colSpan={6}>Записей нет.</td></tr>
            ) : entries.map((e) => (
              <tr key={e.id} className="border-b border-slate-50 align-top hover:bg-slate-50">
                <td className="td whitespace-nowrap text-xs text-slate-500">{dateTime(e.createdAt)}</td>
                <td className="td"><span className="badge-neutral">{ACTION_LABELS[e.action] || e.action}</span></td>
                <td className="td">{e.userEmail || "—"}</td>
                <td className="td text-xs text-slate-500">{e.targetType ? `${e.targetType}${e.targetId ? ` · ${e.targetId.slice(0, 8)}` : ""}` : "—"}</td>
                <td className="td text-xs text-slate-400">{e.ip || "—"}</td>
                <td className="td max-w-xs truncate text-xs text-slate-500" title={e.detail ? JSON.stringify(e.detail) : ""}>
                  {e.detail ? JSON.stringify(e.detail) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
