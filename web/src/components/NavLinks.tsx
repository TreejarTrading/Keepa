"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; adminOnly?: boolean };

const ITEMS: Item[] = [
  { href: "/dashboard", label: "Обзор" },
  { href: "/search", label: "Поиск товаров" },
  { href: "/reports", label: "Отчёты" },
  { href: "/admin/users", label: "Пользователи", adminOnly: true },
  { href: "/admin/audit", label: "Журнал", adminOnly: true },
];

export default function NavLinks({ role }: { role: "ADMIN" | "USER" }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap items-center gap-1">
      {ITEMS.filter((i) => !i.adminOnly || role === "ADMIN").map((i) => {
        const active = pathname === i.href || pathname.startsWith(i.href + "/");
        return (
          <Link
            key={i.href}
            href={i.href}
            className={
              "rounded-lg px-3 py-1.5 text-sm font-medium transition " +
              (active ? "bg-brand text-white" : "text-slate-600 hover:bg-slate-100")
            }
          >
            {i.label}
          </Link>
        );
      })}
    </nav>
  );
}
