import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";
import { buildPlan, type Item } from "@/lib/sourcing";
import { sourcingToItem } from "@/lib/report-mapper";

// Items/suppliers use the same snake_case shape as the Python sourcing layer
// (asin, amazon_sell_price, suppliers:[{platform, price_tiers:[...]}], ...).
const schema = z.object({
  items: z.array(z.record(z.string(), z.any())).min(1, "Передайте хотя бы один товар"),
  baseCurrency: z.string().default("USD"),
  fx: z.record(z.string(), z.number()).optional(),
  dutyPct: z.number().min(0).max(1).optional(),
  defaultOrderQuantity: z.number().int().positive().optional(),
  freightPerKg: z.number().min(0).optional(),
  domain: z.string().optional(),
  save: z.object({ title: z.string().trim().min(1), notes: z.string().trim().optional() }).optional(),
});

export async function POST(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const body = await req.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные данные");
  const { items, baseCurrency, fx, dutyPct, defaultOrderQuantity, freightPerKg, save } = parsed.data;

  const plan = buildPlan(items as unknown as Item[], {
    baseCurrency,
    fx,
    dutyPct,
    defaultOrderQuantity,
    freightPerKg,
  });

  let reportId: string | null = null;
  const ip = clientIp(req);
  if (save) {
    const report = await prisma.report.create({
      data: {
        title: save.title,
        notes: save.notes,
        type: "SOURCING",
        marketplace: (parsed.data.domain || "US").toUpperCase(),
        query: { baseCurrency, dutyPct, freightPerKg } as object,
        createdById: user.id,
        items: { create: plan.rows.map(sourcingToItem) },
      },
      select: { id: true },
    });
    reportId = report.id;
    await writeAudit({
      action: AuditAction.REPORT_CREATE, userId: user.id, userEmail: user.email,
      targetType: "REPORT", targetId: reportId, ip,
      detail: { type: "SOURCING", rows: plan.rows.length, title: save.title },
    });
  }

  return NextResponse.json({ plan, reportId });
}
