import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";
import { analysisToItem, sourcingToItem } from "@/lib/report-mapper";

// List reports with light filtering (type, marketplace, category, text).
export async function GET(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type");
  const marketplace = searchParams.get("marketplace");
  const category = searchParams.get("category");
  const q = searchParams.get("q");

  const reports = await prisma.report.findMany({
    where: {
      ...(type === "AMAZON" || type === "SOURCING" ? { type } : {}),
      ...(marketplace ? { marketplace } : {}),
      ...(q ? { title: { contains: q, mode: "insensitive" } } : {}),
      ...(category ? { items: { some: { rootCategory: category } } } : {}),
    },
    orderBy: { createdAt: "desc" },
    select: {
      id: true, title: true, type: true, marketplace: true, notes: true, createdAt: true,
      createdBy: { select: { email: true, name: true } },
      _count: { select: { items: true } },
    },
  });

  return NextResponse.json({ reports });
}

const createSchema = z.object({
  title: z.string().trim().min(1, "Введите название отчёта"),
  notes: z.string().trim().optional(),
  type: z.enum(["AMAZON", "SOURCING"]).default("AMAZON"),
  marketplace: z.string().default("US"),
  query: z.record(z.string(), z.any()).optional(),
  records: z.array(z.record(z.string(), z.any())).min(1, "Нет товаров для сохранения"),
});

// Persist a report from already-computed records (so saving doesn't spend
// another round of Keepa tokens).
export async function POST(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const body = await req.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");
  const { title, notes, type, marketplace, query, records } = parsed.data;

  const items =
    type === "SOURCING"
      ? records.map((r) => sourcingToItem(r as any))
      : records.map((r) => analysisToItem(r as any));

  const report = await prisma.report.create({
    data: {
      title, notes, type,
      marketplace: marketplace.toUpperCase(),
      query: (query ?? {}) as object,
      createdById: user.id,
      items: { create: items },
    },
    select: { id: true },
  });

  await writeAudit({
    action: AuditAction.REPORT_CREATE, userId: user.id, userEmail: user.email,
    targetType: "REPORT", targetId: report.id, ip: clientIp(req),
    detail: { type, items: items.length, title },
  });

  return NextResponse.json({ reportId: report.id }, { status: 201 });
}
