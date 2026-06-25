import LoginForm from "./LoginForm";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl bg-brand text-xl font-bold text-white">
            K
          </div>
          <h1 className="text-xl font-semibold text-slate-900">Keepa — вход</h1>
          <p className="mt-1 text-sm text-slate-500">
            Подбор товаров и сорсинг для команды
          </p>
        </div>
        <LoginForm next={next || "/dashboard"} />
      </div>
    </div>
  );
}
