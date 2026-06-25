import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";
import UserManager from "@/components/UserManager";

export const dynamic = "force-dynamic";

export default async function AdminUsersPage() {
  const [users, me] = await Promise.all([
    prisma.user.findMany({
      orderBy: { createdAt: "asc" },
      select: { id: true, email: true, name: true, role: true, isActive: true, lastLoginAt: true, createdAt: true },
    }),
    getCurrentUser(),
  ]);

  return <UserManager initialUsers={users as any} currentUserId={me!.id} />;
}
