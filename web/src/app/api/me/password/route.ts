import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { hashPassword, verifyPassword } from "@/lib/auth";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

const schema = z.object({
  currentPassword: z.string().min(1, "Введите текущий пароль"),
  newPassword: z.string().min(8, "Новый пароль не короче 8 символов"),
});

export async function POST(req: Request) {
  const sessionUser = await requireUser();
  if (isResponse(sessionUser)) return sessionUser;

  const body = await req.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");

  const user = await prisma.user.findUnique({ where: { id: sessionUser.id } });
  if (!user) return badRequest("Пользователь не найден");
  if (!(await verifyPassword(parsed.data.currentPassword, user.passwordHash))) {
    return badRequest("Текущий пароль неверен");
  }

  await prisma.user.update({
    where: { id: user.id },
    data: { passwordHash: await hashPassword(parsed.data.newPassword) },
  });
  await writeAudit({
    action: AuditAction.PASSWORD_CHANGE, userId: user.id, userEmail: user.email, ip: clientIp(req),
  });
  return NextResponse.json({ ok: true });
}
