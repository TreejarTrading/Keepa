// Server-side auth: password hashing, session cookie management, current-user
// resolution. Node runtime only (uses bcrypt + Prisma).
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { prisma } from "./db";
import {
  SESSION_COOKIE,
  sessionMaxAgeSeconds,
  signSession,
  verifySession,
  type Role,
  type SessionPayload,
} from "./jwt";

export type CurrentUser = {
  id: string;
  email: string;
  name: string | null;
  role: Role;
};

export function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 10);
}

export function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

export async function startSession(payload: SessionPayload): Promise<void> {
  const token = await signSession(payload);
  const jar = await cookies();
  jar.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: sessionMaxAgeSeconds(),
  });
}

export async function endSession(): Promise<void> {
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const session = await verifySession(token);
  if (!session) return null;
  const user = await prisma.user.findUnique({ where: { id: session.sub } });
  if (!user || !user.isActive) return null;
  return { id: user.id, email: user.email, name: user.name, role: user.role };
}
