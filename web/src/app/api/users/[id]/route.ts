import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { hashPassword } from "@/lib/auth";
import { requireAdmin, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

const patchSchema = z.object({
  name: z.string().trim().max(120).nullable().optional(),
  role: z.enum(["ADMIN", "USER"]).optional(),
  isActive: z.boolean().optional(),
  newPassword: z.string().min(8, "Пароль не короче 8 символов").optional(),
});

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await requireAdmin();
  if (isResponse(admin)) return admin;
  const { id } = await params;

  const target = await prisma.user.findUnique({ where: { id } });
  if (!target) return badRequest("Пользователь не найден");

  const body = await req.json().catch(() => null);
  const parsed = patchSchema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");
  const { name, role, isActive, newPassword } = parsed.data;

  // Guardrails: an admin can't lock themselves out or demote the last admin.
  if (id === admin.id && (isActive === false || role === "USER")) {
    return badRequest("Нельзя деактивировать или понизить собственную учётную запись");
  }
  if ((role === "USER" || isActive === false) && target.role === "ADMIN") {
    const admins = await prisma.user.count({ where: { role: "ADMIN", isActive: true } });
    if (admins <= 1) return badRequest("Нельзя убрать последнего активного администратора");
  }

  const data: Record<string, unknown> = {};
  if (name !== undefined) data.name = name;
  if (role !== undefined) data.role = role;
  if (isActive !== undefined) data.isActive = isActive;
  if (newPassword) data.passwordHash = await hashPassword(newPassword);

  const user = await prisma.user.update({
    where: { id },
    data,
    select: { id: true, email: true, name: true, role: true, isActive: true, lastLoginAt: true, createdAt: true },
  });

  const ip = clientIp(req);
  if (newPassword) {
    await writeAudit({
      action: AuditAction.USER_PASSWORD_RESET, userId: admin.id, userEmail: admin.email,
      targetType: "USER", targetId: id, ip, detail: { email: user.email },
    });
  }
  if (isActive === false) {
    await writeAudit({
      action: AuditAction.USER_DEACTIVATE, userId: admin.id, userEmail: admin.email,
      targetType: "USER", targetId: id, ip, detail: { email: user.email },
    });
  }
  if (name !== undefined || role !== undefined || isActive === true) {
    await writeAudit({
      action: AuditAction.USER_UPDATE, userId: admin.id, userEmail: admin.email,
      targetType: "USER", targetId: id, ip, detail: { name, role, isActive },
    });
  }

  return NextResponse.json({ user });
}
