import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { hashPassword } from "@/lib/auth";
import { requireAdmin, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

export async function GET() {
  const admin = await requireAdmin();
  if (isResponse(admin)) return admin;

  const users = await prisma.user.findMany({
    orderBy: { createdAt: "asc" },
    select: {
      id: true, email: true, name: true, role: true, isActive: true,
      lastLoginAt: true, createdAt: true,
    },
  });
  return NextResponse.json({ users });
}

const createSchema = z.object({
  email: z.string().email("Некорректный email"),
  name: z.string().trim().max(120).optional(),
  password: z.string().min(8, "Пароль не короче 8 символов"),
  role: z.enum(["ADMIN", "USER"]).default("USER"),
});

export async function POST(req: Request) {
  const admin = await requireAdmin();
  if (isResponse(admin)) return admin;

  const body = await req.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");

  const email = parsed.data.email.toLowerCase().trim();
  const exists = await prisma.user.findUnique({ where: { email } });
  if (exists) return badRequest("Пользователь с таким email уже существует");

  const user = await prisma.user.create({
    data: {
      email,
      name: parsed.data.name || null,
      role: parsed.data.role,
      passwordHash: await hashPassword(parsed.data.password),
      createdById: admin.id,
    },
    select: { id: true, email: true, name: true, role: true, isActive: true, createdAt: true },
  });

  await writeAudit({
    action: AuditAction.USER_CREATE,
    userId: admin.id,
    userEmail: admin.email,
    targetType: "USER",
    targetId: user.id,
    ip: clientIp(req),
    detail: { email: user.email, role: user.role },
  });

  return NextResponse.json({ user }, { status: 201 });
}
