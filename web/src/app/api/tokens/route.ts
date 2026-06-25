import { NextResponse } from "next/server";
import { requireUser, isResponse } from "@/lib/api";
import { tokenStatus, KeepaError } from "@/lib/keepa";

export async function GET() {
  const user = await requireUser();
  if (isResponse(user)) return user;
  try {
    return NextResponse.json(await tokenStatus());
  } catch (err) {
    const status = err instanceof KeepaError ? err.status : 500;
    return NextResponse.json({ error: (err as Error).message }, { status });
  }
}
