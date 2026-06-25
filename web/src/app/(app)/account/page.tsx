import { getCurrentUser } from "@/lib/auth";
import PasswordForm from "@/components/PasswordForm";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const user = await getCurrentUser();
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold text-slate-900">Мой аккаунт</h1>
      <div className="card max-w-md p-5 text-sm">
        <div className="flex justify-between py-1"><span className="text-slate-500">Email</span><span className="font-medium">{user?.email}</span></div>
        <div className="flex justify-between py-1"><span className="text-slate-500">Имя</span><span className="font-medium">{user?.name || "—"}</span></div>
        <div className="flex justify-between py-1"><span className="text-slate-500">Роль</span><span className="font-medium">{user?.role === "ADMIN" ? "Администратор" : "Пользователь"}</span></div>
      </div>
      <div>
        <h2 className="mb-2 font-semibold text-slate-900">Сменить пароль</h2>
        <PasswordForm />
      </div>
    </div>
  );
}
