import { NextResponse } from "next/server";
import { getCurrentUser, endSession } from "@/lib/auth";
import { writeAudit, AuditAction, clientIp } from "@/lib/audit";

export async function POST(req: Request) {
  const user = await getCurrentUser();
  await endSession();
  if (user) {
    await writeAudit({
      action: AuditAction.LOGOUT,
      userId: user.id,
      userEmail: user.email,
      ip: clientIp(req),
    });
  }
  return NextResponse.json({ ok: true });
}
