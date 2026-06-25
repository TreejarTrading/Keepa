"use client";

import { useState } from "react";
import { dateTime } from "@/lib/format";

type U = {
  id: string;
  email: string;
  name: string | null;
  role: "ADMIN" | "USER";
  isActive: boolean;
  lastLoginAt: string | Date | null;
  createdAt: string | Date;
};

export default function UserManager({
  initialUsers, currentUserId,
}: {
  initialUsers: U[];
  currentUserId: string;
}) {
  const [users, setUsers] = useState<U[]>(initialUsers);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"ADMIN" | "USER">("USER");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function patch(id: string, body: Record<string, unknown>) {
    const res = await fetch(`/api/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setMsg({ kind: "err", text: data.error || "Ошибка обновления" });
      return null;
    }
    setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, ...data.user } : u)));
    setMsg({ kind: "ok", text: "Сохранено" });
    return data.user as U;
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name: name || undefined, password, role }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMsg({ kind: "err", text: data.error || "Не удалось создать" });
        return;
      }
      setUsers((prev) => [...prev, data.user]);
      setEmail(""); setName(""); setPassword(""); setRole("USER");
      setMsg({ kind: "ok", text: `Создан ${data.user.email}` });
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(u: U) {
    const np = prompt(`Новый пароль для ${u.email} (минимум 8 символов):`);
    if (!np) return;
    if (np.length < 8) { setMsg({ kind: "err", text: "Пароль слишком короткий" }); return; }
    await patch(u.id, { newPassword: np });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Пользователи</h1>
      </div>

      {msg && (
        <div className={(msg.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700") + " rounded-lg px-3 py-2 text-sm"}>
          {msg.text}
        </div>
      )}

      <form onSubmit={createUser} className="card grid grid-cols-1 gap-3 p-4 md:grid-cols-5">
        <div className="md:col-span-2">
          <label className="label">Email (логин)</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" />
        </div>
        <div>
          <label className="label">Имя</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Пароль</label>
          <input className="input" type="text" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="мин. 8 символов" />
        </div>
        <div>
          <label className="label">Роль</label>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value as "ADMIN" | "USER")}>
            <option value="USER">Пользователь</option>
            <option value="ADMIN">Администратор</option>
          </select>
        </div>
        <div className="md:col-span-5">
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Создание…" : "Создать пользователя"}
          </button>
          <span className="ml-3 text-xs text-slate-500">Пароль задаёте вы и передаёте пользователю.</span>
        </div>
      </form>

      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="th">Email</th>
              <th className="th">Имя</th>
              <th className="th">Роль</th>
              <th className="th">Статус</th>
              <th className="th">Последний вход</th>
              <th className="th">Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const self = u.id === currentUserId;
              return (
                <tr key={u.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="td font-medium">{u.email}{self && <span className="ml-2 text-xs text-slate-400">(вы)</span>}</td>
                  <td className="td">{u.name || "—"}</td>
                  <td className="td">
                    <select
                      className="input !py-1" value={u.role} disabled={self}
                      onChange={(e) => patch(u.id, { role: e.target.value })}
                    >
                      <option value="USER">Пользователь</option>
                      <option value="ADMIN">Администратор</option>
                    </select>
                  </td>
                  <td className="td">
                    {u.isActive
                      ? <span className="badge-buy">активен</span>
                      : <span className="badge-skip">отключён</span>}
                  </td>
                  <td className="td text-xs text-slate-500">{u.lastLoginAt ? dateTime(u.lastLoginAt) : "—"}</td>
                  <td className="td">
                    <div className="flex gap-2">
                      <button className="btn-ghost !py-1" onClick={() => resetPassword(u)}>Сменить пароль</button>
                      {!self && (
                        <button
                          className={(u.isActive ? "btn-danger" : "btn-ghost") + " !py-1"}
                          onClick={() => patch(u.id, { isActive: !u.isActive })}
                        >
                          {u.isActive ? "Отключить" : "Включить"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
