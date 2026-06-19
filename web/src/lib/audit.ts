import { prisma } from "./db";
import type { Prisma } from "@prisma/client";

// Well-known action names (free-form string in the DB, listed here for clarity).
export const AuditAction = {
  LOGIN: "LOGIN",
  LOGIN_FAILED: "LOGIN_FAILED",
  LOGOUT: "LOGOUT",
  PASSWORD_CHANGE: "PASSWORD_CHANGE",
  USER_CREATE: "USER_CREATE",
  USER_UPDATE: "USER_UPDATE",
  USER_DEACTIVATE: "USER_DEACTIVATE",
  USER_PASSWORD_RESET: "USER_PASSWORD_RESET",
  SEARCH_RUN: "SEARCH_RUN",
  REPORT_CREATE: "REPORT_CREATE",
  REPORT_VIEW: "REPORT_VIEW",
  REPORT_DELETE: "REPORT_DELETE",
  VERDICT_OVERRIDE: "VERDICT_OVERRIDE",
  SAVED_QUERY_CREATE: "SAVED_QUERY_CREATE",
  SAVED_QUERY_DELETE: "SAVED_QUERY_DELETE",
} as const;

export type AuditParams = {
  action: string;
  userId?: string | null;
  userEmail?: string | null;
  targetType?: string;
  targetId?: string;
  ip?: string | null;
  detail?: Prisma.InputJsonValue;
};

/** Append one row to the audit journal. Never throws — logging must not break
 *  the action it records. */
export async function writeAudit(params: AuditParams): Promise<void> {
  try {
    await prisma.auditLog.create({
      data: {
        action: params.action,
        userId: params.userId ?? null,
        userEmail: params.userEmail ?? null,
        targetType: params.targetType,
        targetId: params.targetId,
        ip: params.ip ?? null,
        detail: params.detail,
      },
    });
  } catch (err) {
    console.error("[audit] failed to write entry", params.action, err);
  }
}

/** Best-effort client IP from request headers (works behind a proxy). */
export function clientIp(req: Request): string | null {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0]!.trim();
  return req.headers.get("x-real-ip");
}
