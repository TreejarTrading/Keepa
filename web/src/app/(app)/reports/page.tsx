import Link from "next/link";
import { prisma } from "@/lib/db";
import { dateTime } from "@/lib/format";
import type { Prisma } from "@prisma/client";

export const dynamic = "force-dynamic";

export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string; category?: string; q?: string; marketplace?: string }>;
}) {
  const sp = await searchParams;
  const type = sp.type === "AMAZON" || sp.type === "SOURCING" ? sp.type : undefined;

  const where: Prisma.ReportWhereInput = {
    ...(type ? { type } : {}),
    ...(sp.marketplace ? { marketplace: sp.marketplace } : {}),
    ...(sp.q ? { title: { contains: sp.q, mode: "insensitive" } } : {}),
    ...(sp.category ? { items: { some: { rootCategory: sp.category } } } : {}),
  };

  const [reports, cats] = await Promise.all([
    prisma.report.findMany({
      where,
      orderBy: { createdAt: "desc" },
      select: {
        id: true, title: true, type: true, marketplace: true, notes: true, createdAt: true,
        createdBy: { select: { email: true, name: true } },
        _count: { select: { items: true } },
      },
    }),
    prisma.reportItem.findMany({
      where: { rootCategory: { not: null } },
      distinct: ["rootCategory"],
      select: { rootCategory: true },
      orderBy: { rootCategory: "asc" },
    }),
  ]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Отчёты</h1>
        <Link href="/search" className="btn-primary">Новый поиск</Link>
      </div>

      <form className="card grid grid-cols-2 gap-3 p-4 md:grid-cols-5" method="get">
        <div>
          <label className="label">Тип</label>
          <select name="type" defaultValue={sp.type || ""} className="input">
            <option value="">Все</option>
            <option value="AMAZON">Amazon</option>
            <option value="SOURCING">Сорсинг</option>
          </select>
        </div>
        <div>
          <label className="label">Категория</label>
          <select name="category" defaultValue={sp.category || ""} className="input">
            <option value="">Все категории</option>
            {cats.map((c) => (
              <option key={c.rootCategory} value={c.rootCategory!}>{c.rootCategory}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Рынок</label>
          <input name="marketplace" defaultValue={sp.marketplace || ""} className="input" placeholder="US" />
        </div>
        <div className="md:col-span-1">
          <label className="label">Поиск по названию</label>
          <input name="q" defaultValue={sp.q || ""} className="input" />
        </div>
        <div className="flex items-end">
          <button className="btn-primary w-full" type="submit">Применить</button>
        </div>
      </form>

      <div className="card">
        {reports.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-slate-500">
            Ничего не найдено. Измените фильтры или <Link href="/search" className="text-brand hover:underline">запустите поиск</Link>.
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="th">Название</th>
                <th className="th">Тип</th>
                <th className="th">Рынок</th>
                <th className="th">Товаров</th>
                <th className="th">Автор</th>
                <th className="th">Создан</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="td font-medium">
                    <Link href={`/reports/${r.id}`} className="text-brand hover:underline">{r.title}</Link>
                    {r.notes && <div className="text-xs text-slate-400">{r.notes}</div>}
                  </td>
                  <td className="td">{r.type === "AMAZON" ? "Amazon" : "Сорсинг"}</td>
                  <td className="td">{r.marketplace}</td>
                  <td className="td">{r._count.items}</td>
                  <td className="td">{r.createdBy?.name || r.createdBy?.email}</td>
                  <td className="td">{dateTime(r.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
