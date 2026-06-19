import SearchClient from "@/components/SearchClient";

export const dynamic = "force-dynamic";

export default function SearchPage() {
  const defaultDomain = (process.env.KEEPA_DEFAULT_DOMAIN || "US").toUpperCase();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Поиск товаров</h1>
        <p className="text-sm text-slate-500">
          Живой поиск по Keepa с метриками решения и авто-вердиктом. Результат можно сохранить как отчёт.
        </p>
      </div>
      <SearchClient defaultDomain={defaultDomain} />
    </div>
  );
}
