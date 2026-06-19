import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

// Saved searches are shared across the team (like reports): everyone can list
// and run them; only the author or an admin can delete (see [id]/route.ts).
export async function GET(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type");

  const queries = await prisma.savedQuery.findMany({
    where: type === "AMAZON" || type === "SOURCING" ? { type } : {},
    orderBy: { updatedAt: "desc" },
    select: {
      id: true, name: true, type: true, params: true, createdAt: true, updatedAt: true,
      createdById: true,
    },
  });
  return NextResponse.json({ queries });
}

const createSchema = z.object({
  name: z.string().trim().min(1, "Введите название поиска").max(120),
  type: z.enum(["AMAZON", "SOURCING"]).default("AMAZON"),
  params: z.record(z.string(), z.any()),
});

export async function POST(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const body = await req.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");
  const { name, type, params } = parsed.data;

  const query = await prisma.savedQuery.create({
    data: { name, type, params: params as object, createdById: user.id },
    select: { id: true, name: true, type: true, params: true, createdAt: true, updatedAt: true, createdById: true },
  });

  await writeAudit({
    action: AuditAction.SAVED_QUERY_CREATE, userId: user.id, userEmail: user.email,
    targetType: "SAVED_QUERY", targetId: query.id, ip: clientIp(req), detail: { name, type },
  });

  return NextResponse.json({ query }, { status: 201 });
}
