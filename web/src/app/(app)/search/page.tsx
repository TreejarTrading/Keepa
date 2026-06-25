import SearchClient from "@/components/SearchClient";

export const dynamic = "force-dynamic";

export default function SearchPage() {
  const defaultDomain = (process.env.KEEPA_DEFAULT_DOMAIN || "US").toUpperCase();
  const keepaConfigured = Boolean(process.env.KEEPA_API_KEY);
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Поиск товаров</h1>
        <p className="text-sm text-slate-500">
          Живой поиск по Keepa с метриками решения и авто-вердиктом. Результат можно сохранить как отчёт.
        </p>
      </div>
      {!keepaConfigured && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Ключ <code>KEEPA_API_KEY</code> не задан в окружении — живой поиск недоступен. Добавьте ключ в
          <code> .env</code> и перезапустите приложение. Остальные разделы (отчёты, сорсинг, пользователи)
          работают без него.
        </div>
      )}
      <SearchClient defaultDomain={defaultDomain} />
    </div>
  );
}
