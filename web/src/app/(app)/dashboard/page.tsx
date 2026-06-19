import Link from "next/link";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { dateTime, verdictClass } from "@/lib/format";
import TokenStatus from "@/components/TokenStatus";

export const dynamic = "force-dynamic";

function StatCard({ label, value, href }: { label: string; value: number | string; href?: string }) {
  const body = (
    <div className="card p-4 transition hover:shadow-md">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export default async function DashboardPage() {
  const user = await getCurrentUser();
  const isAdmin = user?.role === "ADMIN";

  const [reportCount, amazonCount, sourcingCount, itemCount, userCount, verdictGroups, recent] = await Promise.all([
    prisma.report.count(),
    prisma.report.count({ where: { type: "AMAZON" } }),
    prisma.report.count({ where: { type: "SOURCING" } }),
    prisma.reportItem.count(),
    isAdmin ? prisma.user.count() : Promise.resolve(0),
    prisma.reportItem.groupBy({ by: ["verdict"], _count: { _all: true } }),
    prisma.report.findMany({
      orderBy: { createdAt: "desc" },
      take: 6,
      select: {
        id: true, title: true, type: true, marketplace: true, createdAt: true,
        _count: { select: { items: true } },
        createdBy: { select: { email: true, name: true } },
      },
    }),
  ]);

  const verdicts = verdictGroups
    .filter((g) => g.verdict)
    .map((g) => ({ verdict: g.verdict as string, count: g._count._all }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Обзор</h1>
          <p className="text-sm text-slate-500">Добро пожаловать, {user?.name || user?.email}.</p>
        </div>
        <Link href="/search" className="btn-primary">Новый поиск</Link>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-5">
        <StatCard label="Отчётов" value={reportCount} href="/reports" />
        <StatCard label="Amazon" value={amazonCount} href="/reports?type=AMAZON" />
        <StatCard label="Сорсинг" value={sourcingCount} href="/reports?type=SOURCING" />
        <StatCard label="Товаров" value={itemCount} />
        {isAdmin ? <StatCard label="Пользователей" value={userCount} href="/admin/users" /> : <TokenStatus />}
      </div>
      {isAdmin && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-5">
          <TokenStatus />
        </div>
      )}

      {verdicts.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Вердикты по товарам
          </div>
          <div className="flex flex-wrap gap-2">
            {verdicts.map((v) => (
              <span key={v.verdict} className={verdictClass(v.verdict)}>{v.verdict}: {v.count}</span>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="font-semibold text-slate-900">Последние отчёты</h2>
          <Link href="/reports" className="text-sm text-brand hover:underline">Все отчёты →</Link>
        </div>
        {recent.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">
            Отчётов пока нет. <Link href="/search" className="text-brand hover:underline">Запустите первый поиск</Link>.
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
              {recent.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="td font-medium">
                    <Link href={`/reports/${r.id}`} className="text-brand hover:underline">{r.title}</Link>
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
