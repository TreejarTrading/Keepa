import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

export async function DELETE(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  if (isResponse(user)) return user;
  const { id } = await params;

  const query = await prisma.savedQuery.findUnique({
    where: { id },
    select: { id: true, name: true, createdById: true },
  });
  if (!query) return badRequest("Поиск не найден");
  // Only the author or an admin can delete a saved search.
  if (query.createdById !== user.id && user.role !== "ADMIN") {
    return NextResponse.json({ error: "Можно удалять только свои поиски" }, { status: 403 });
  }

  await prisma.savedQuery.delete({ where: { id } });
  await writeAudit({
    action: AuditAction.SAVED_QUERY_DELETE, userId: user.id, userEmail: user.email,
    targetType: "SAVED_QUERY", targetId: id, ip: clientIp(req), detail: { name: query.name },
  });
  return NextResponse.json({ ok: true });
}
