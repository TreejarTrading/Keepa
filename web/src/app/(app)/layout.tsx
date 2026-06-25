import { redirect } from "next/navigation";
import Link from "next/link";
import { getCurrentUser } from "@/lib/auth";
import NavLinks from "@/components/NavLinks";
import LogoutButton from "@/components/LogoutButton";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-3">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-brand text-white">K</span>
            Keepa
          </Link>
          <NavLinks role={user.role} />
          <div className="ml-auto flex items-center gap-3 text-sm">
            <Link href="/account" className="text-slate-600 hover:text-slate-900">
              {user.name || user.email}
              {user.role === "ADMIN" && (
                <span className="ml-2 badge-neutral">админ</span>
              )}
            </Link>
            <LogoutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
