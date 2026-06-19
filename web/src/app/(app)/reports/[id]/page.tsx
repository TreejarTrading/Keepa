import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import { writeAudit, AuditAction } from "@/lib/audit";
import { dateTime } from "@/lib/format";
import ReportView from "@/components/ReportView";

export const dynamic = "force-dynamic";

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [report, user] = await Promise.all([
    prisma.report.findUnique({
      where: { id },
      include: {
        createdBy: { select: { email: true, name: true } },
        items: { orderBy: { sellPrice: "desc" } },
      },
    }),
    getCurrentUser(),
  ]);
  if (!report) notFound();

  await writeAudit({
    action: AuditAction.REPORT_VIEW,
    userId: user?.id,
    userEmail: user?.email,
    targetType: "REPORT",
    targetId: report.id,
    detail: { title: report.title },
  });

  const canDelete = user?.role === "ADMIN" || report.createdById === user?.id;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Link href="/reports" className="hover:underline">Отчёты</Link>
            <span>/</span>
            <span>{report.type === "AMAZON" ? "Amazon" : "Сорсинг"}</span>
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">{report.title}</h1>
          <p className="text-sm text-slate-500">
            {report.marketplace} · {report.items.length} товаров · автор {report.createdBy?.name || report.createdBy?.email} · {dateTime(report.createdAt)}
          </p>
          {report.notes && <p className="mt-1 text-sm text-slate-600">{report.notes}</p>}
        </div>
      </div>

      <ReportView
        reportId={report.id}
        type={report.type}
        marketplace={report.marketplace}
        items={report.items as any}
        canDelete={canDelete}
      />
    </div>
  );
}
