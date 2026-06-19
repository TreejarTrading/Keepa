"use client";

import { useState } from "react";

export default function PasswordForm() {
  const [currentPassword, setCurrent] = useState("");
  const [newPassword, setNew] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/me/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword, newPassword }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMsg({ kind: "err", text: data.error || "Не удалось сменить пароль" });
        return;
      }
      setMsg({ kind: "ok", text: "Пароль обновлён" });
      setCurrent(""); setNew("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card max-w-md space-y-4 p-5">
      <div>
        <label className="label">Текущий пароль</label>
        <input className="input" type="password" required value={currentPassword} onChange={(e) => setCurrent(e.target.value)} />
      </div>
      <div>
        <label className="label">Новый пароль</label>
        <input className="input" type="password" required minLength={8} value={newPassword} onChange={(e) => setNew(e.target.value)} placeholder="минимум 8 символов" />
      </div>
      {msg && (
        <p className={(msg.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700") + " rounded-lg px-3 py-2 text-sm"}>
          {msg.text}
        </p>
      )}
      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? "Сохранение…" : "Сменить пароль"}
      </button>
    </form>
  );
}
