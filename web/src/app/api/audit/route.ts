import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { requireAdmin, isResponse } from "@/lib/api";

// Audit journal viewer (admin only) with action/user filters + pagination.
export async function GET(req: Request) {
  const admin = await requireAdmin();
  if (isResponse(admin)) return admin;

  const { searchParams } = new URL(req.url);
  const action = searchParams.get("action") || undefined;
  const userEmail = searchParams.get("user") || undefined;
  const take = Math.min(Number(searchParams.get("take") || "100"), 500);
  const skip = Math.max(Number(searchParams.get("skip") || "0"), 0);

  const where = {
    ...(action ? { action } : {}),
    ...(userEmail ? { userEmail: { contains: userEmail, mode: "insensitive" as const } } : {}),
  };

  const [entries, total] = await Promise.all([
    prisma.auditLog.findMany({ where, orderBy: { createdAt: "desc" }, take, skip }),
    prisma.auditLog.count({ where }),
  ]);

  return NextResponse.json({ entries, total, take, skip });
}
