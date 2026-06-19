import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";
import { buildSelection, productFinder, queryProducts, KeepaError } from "@/lib/keepa";
import { buildRecord } from "@/lib/analysis";
import { analysisToItem } from "@/lib/report-mapper";

const filtersSchema = z.object({
  title: z.string().trim().optional(),
  categoryId: z.number().int().optional(),
  brand: z.string().trim().optional(),
  minPrice: z.number().optional(),
  maxPrice: z.number().optional(),
  minRating: z.number().min(0).max(5).optional(),
  maxSalesRank: z.number().int().optional(),
  minReviewCount: z.number().int().optional(),
  maxOfferCount: z.number().int().optional(),
  minMonthlySold: z.number().int().optional(),
});

const schema = z.object({
  filters: filtersSchema.default({}),
  domain: z.string().optional(),
  limit: z.number().int().min(1).max(100).default(25),
  statsDays: z.number().int().min(1).max(365).optional(),
  save: z.object({ title: z.string().trim().min(1), notes: z.string().trim().optional() }).optional(),
});

export async function POST(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const body = await req.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return badRequest(parsed.error.issues[0]?.message ?? "Неверные параметры");
  const { filters, domain, limit, statsDays, save } = parsed.data;

  const ip = clientIp(req);
  try {
    const selection = buildSelection(filters);
    const asins = await productFinder(selection, { domain, limit });
    const products = asins.length ? await queryProducts(asins, { domain, statsDays }) : [];
    const records = products.map((p) => buildRecord(p, { domain, statsDays }));

    let reportId: string | null = null;
    if (save) {
      const report = await prisma.report.create({
        data: {
          title: save.title,
          notes: save.notes,
          type: "AMAZON",
          marketplace: (domain || "US").toUpperCase(),
          query: { filters, limit } as object,
          createdById: user.id,
          items: { create: records.map(analysisToItem) },
        },
        select: { id: true },
      });
      reportId = report.id;
      await writeAudit({
        action: AuditAction.REPORT_CREATE, userId: user.id, userEmail: user.email,
        targetType: "REPORT", targetId: reportId, ip,
        detail: { type: "AMAZON", items: records.length, title: save.title },
      });
    }

    await writeAudit({
      action: AuditAction.SEARCH_RUN, userId: user.id, userEmail: user.email, ip,
      detail: { filters, domain: (domain || "US").toUpperCase(), found: asins.length, returned: records.length, saved: !!reportId },
    });

    return NextResponse.json({ asinsFound: asins.length, records, reportId });
  } catch (err) {
    if (err instanceof KeepaError) {
      await writeAudit({
        action: AuditAction.SEARCH_RUN, userId: user.id, userEmail: user.email, ip,
        detail: { filters, error: err.message },
      });
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    console.error("[search] error", err);
    return NextResponse.json({ error: "Ошибка поиска. См. логи сервера." }, { status: 500 });
  }
}
