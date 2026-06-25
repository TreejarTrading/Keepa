// Edge-safe session token helpers (jose only — no Node APIs, no Prisma) so they
// can be used from both middleware (Edge runtime) and server code.
import { SignJWT, jwtVerify } from "jose";

export const SESSION_COOKIE = "keepa_session";

export type Role = "ADMIN" | "USER";
export type SessionPayload = { sub: string; email: string; role: Role };

function secretKey(): Uint8Array {
  const secret = process.env.AUTH_SECRET || "dev-insecure-secret-change-me";
  return new TextEncoder().encode(secret);
}

export function sessionMaxAgeSeconds(): number {
  const hours = Number(process.env.AUTH_SESSION_HOURS || "12");
  return Math.max(1, hours) * 60 * 60;
}

export async function signSession(payload: SessionPayload): Promise<string> {
  return new SignJWT({ email: payload.email, role: payload.role })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(payload.sub)
    .setIssuedAt()
    .setExpirationTime(`${Number(process.env.AUTH_SESSION_HOURS || "12")}h`)
    .sign(secretKey());
}

export async function verifySession(token: string): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, secretKey());
    if (!payload.sub) return null;
    return {
      sub: String(payload.sub),
      email: String(payload.email ?? ""),
      role: payload.role === "ADMIN" ? "ADMIN" : "USER",
    };
  } catch {
    return null;
  }
}
