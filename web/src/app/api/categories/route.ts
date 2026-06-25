import { NextResponse } from "next/server";
import { requireUser, isResponse, badRequest } from "@/lib/api";
import { KeepaError } from "@/lib/keepa";
import { searchCategoriesCached } from "@/lib/categories";

export async function GET(req: Request) {
  const user = await requireUser();
  if (isResponse(user)) return user;

  const { searchParams } = new URL(req.url);
  const term = (searchParams.get("term") || "").trim();
  const domain = searchParams.get("domain") || undefined;
  if (term.length < 2) return badRequest("Введите минимум 2 символа");

  try {
    const { categories, source } = await searchCategoriesCached(term, { domain });
    return NextResponse.json({ categories: categories.slice(0, 50), source });
  } catch (err) {
    if (err instanceof KeepaError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return NextResponse.json({ error: "Не удалось найти категории" }, { status: 500 });
  }
}
