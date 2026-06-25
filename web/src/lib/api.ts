import { NextResponse } from "next/server";
import { getCurrentUser, type CurrentUser } from "./auth";

export type { CurrentUser };

export function unauthorized() {
  return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
}
export function forbidden() {
  return NextResponse.json({ error: "Недостаточно прав" }, { status: 403 });
}
export function badRequest(error: string, extra?: Record<string, unknown>) {
  return NextResponse.json({ error, ...extra }, { status: 400 });
}
export function serverError(error: string, status = 500) {
  return NextResponse.json({ error }, { status });
}

/** Resolve the current user or return a 401 response. */
export async function requireUser(): Promise<CurrentUser | NextResponse> {
  const user = await getCurrentUser();
  return user ?? unauthorized();
}

/** Resolve an ADMIN user or return a 401/403 response. */
export async function requireAdmin(): Promise<CurrentUser | NextResponse> {
  const user = await getCurrentUser();
  if (!user) return unauthorized();
  if (user.role !== "ADMIN") return forbidden();
  return user;
}

export function isResponse(x: unknown): x is NextResponse {
  return x instanceof NextResponse;
}
