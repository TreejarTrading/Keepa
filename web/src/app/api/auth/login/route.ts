import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { verifyPassword, startSession } from "@/lib/auth";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

const schema = z.object({
  email: z.string().email("Введите корректный email"),
  password: z.string().min(1, "Введите пароль"),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? "Неверные данные" },
      { status: 400 },
    );
  }
  const email = parsed.data.email.toLowerCase().trim();
  const ip = clientIp(req);

  const user = await prisma.user.findUnique({ where: { email } });
  const ok = user && user.isActive && (await verifyPassword(parsed.data.password, user.passwordHash));
  if (!user || !ok) {
    await writeAudit({
      action: AuditAction.LOGIN_FAILED,
      userId: user?.id ?? null,
      userEmail: email,
      ip,
      detail: { reason: !user ? "no_user" : !user.isActive ? "inactive" : "bad_password" },
    });
    return NextResponse.json({ error: "Неверный email или пароль" }, { status: 401 });
  }

  await startSession({ sub: user.id, email: user.email, role: user.role });
  await prisma.user.update({ where: { id: user.id }, data: { lastLoginAt: new Date() } });
  await writeAudit({ action: AuditAction.LOGIN, userId: user.id, userEmail: user.email, ip });

  return NextResponse.json({ ok: true, role: user.role });
}
