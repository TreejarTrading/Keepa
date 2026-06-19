"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || "Не удалось войти");
        return;
      }
      router.replace(next.startsWith("/") ? next : "/dashboard");
      router.refresh();
    } catch {
      setError("Сеть недоступна. Повторите попытку.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-4 p-6">
      <div>
        <label className="label" htmlFor="email">Email</label>
        <input
          id="email" type="email" autoComplete="username" required
          className="input" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
      </div>
      <div>
        <label className="label" htmlFor="password">Пароль</label>
        <input
          id="password" type="password" autoComplete="current-password" required
          className="input" value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
        />
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" className="btn-primary w-full" disabled={busy}>
        {busy ? "Вход…" : "Войти"}
      </button>
    </form>
  );
}
