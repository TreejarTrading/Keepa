// Category search with a PostgreSQL-backed cache (model KeepaCategory).
//
// Strategy: prefer a live Keepa lookup (authoritative) and enrich the cache
// with whatever it returns. If the live call fails — most importantly when no
// KEEPA_API_KEY is configured — fall back to the cache so the category picker
// still works from categories seen on earlier searches.
import { prisma } from "./db";
import { searchCategories, normalizeDomain, type CategoryHit } from "./keepa";

export type CategoryResult = { categories: CategoryHit[]; source: "live" | "cache" };

/** Persist live results so future searches (and offline ones) can reuse them. */
async function cacheCategories(domain: string, hits: CategoryHit[]): Promise<void> {
  try {
    await Promise.all(
      hits.map((c) => {
        const catId = BigInt(c.catId);
        const parentId = c.parentId ? BigInt(c.parentId) : null;
        return prisma.keepaCategory.upsert({
          where: { domain_catId: { domain, catId } },
          create: { domain, catId, name: c.name, parentId },
          update: { name: c.name, parentId },
        });
      }),
    );
  } catch (err) {
    // Caching is best-effort; never fail the user's search because of it.
    console.error("[categories] cache write failed", err);
  }
}

/** Read cached categories for a domain whose name matches the term. */
async function readCache(domain: string, term: string): Promise<CategoryHit[]> {
  const rows = await prisma.keepaCategory.findMany({
    where: { domain, name: { contains: term, mode: "insensitive" } },
    orderBy: { name: "asc" },
    take: 50,
  });
  return rows.map((r) => ({
    catId: String(r.catId),
    name: r.name,
    parentId: r.parentId == null ? null : String(r.parentId),
  }));
}

/**
 * Search categories live and cache the result; on failure, serve from cache.
 * Re-throws the original error only when the cache has nothing to offer.
 */
export async function searchCategoriesCached(
  term: string,
  opts: { domain?: string } = {},
): Promise<CategoryResult> {
  const domain = normalizeDomain(opts.domain);
  try {
    const categories = await searchCategories(term, { domain });
    await cacheCategories(domain, categories);
    return { categories, source: "live" };
  } catch (err) {
    const cached = await readCache(domain, term);
    if (cached.length > 0) return { categories: cached, source: "cache" };
    throw err;
  }
}
