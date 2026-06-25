import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  if (isResponse(user)) return user;
  const { id } = await params;

  const report = await prisma.report.findUnique({
    where: { id },
    include: {
      createdBy: { select: { email: true, name: true } },
      items: { orderBy: { createdAt: "asc" } },
    },
  });
  if (!report) return badRequest("Отчёт не найден");
  return NextResponse.json({ report });
}

export async function DELETE(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  if (isResponse(user)) return user;
  const { id } = await params;

  const report = await prisma.report.findUnique({ where: { id }, select: { id: true, title: true, createdById: true } });
  if (!report) return badRequest("Отчёт не найден");
  // Only the owner or an admin can delete a report.
  if (report.createdById !== user.id && user.role !== "ADMIN") {
    return NextResponse.json({ error: "Можно удалять только свои отчёты" }, { status: 403 });
  }

  await prisma.report.delete({ where: { id } });
  await writeAudit({
    action: AuditAction.REPORT_DELETE, userId: user.id, userEmail: user.email,
    targetType: "REPORT", targetId: id, ip: clientIp(req), detail: { title: report.title },
  });
  return NextResponse.json({ ok: true });
}
