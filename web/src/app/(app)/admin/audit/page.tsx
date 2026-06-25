import { prisma } from "@/lib/db";
import { AuditAction } from "@/lib/audit";
import AuditTable from "@/components/AuditTable";

export const dynamic = "force-dynamic";

export default async function AdminAuditPage() {
  const entries = await prisma.auditLog.findMany({
    orderBy: { createdAt: "desc" },
    take: 100,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Журнал действий</h1>
        <p className="text-sm text-slate-500">Кто что делал в системе: входы, поиски, отчёты, изменения пользователей.</p>
      </div>
      <AuditTable initialEntries={entries as any} actions={Object.values(AuditAction)} />
    </div>
  );
}
