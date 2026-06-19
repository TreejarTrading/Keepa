/**
 * Creates (or re-activates) the initial administrator from environment vars.
 * Idempotent: the password is only set when the account is first created, so
 * restarting the container never clobbers a password the admin has changed.
 */
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const email = (process.env.ADMIN_EMAIL || "kadievdavid37@gmail.com").toLowerCase().trim();
  const password = process.env.ADMIN_PASSWORD || "change-this-on-first-login";
  const name = process.env.ADMIN_NAME || "Administrator";

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    await prisma.user.update({
      where: { email },
      data: { role: "ADMIN", isActive: true },
    });
    console.log(`Admin already present, ensured ADMIN+active: ${email}`);
    return;
  }

  const passwordHash = await bcrypt.hash(password, 10);
  await prisma.user.create({
    data: { email, name, passwordHash, role: "ADMIN", isActive: true },
  });
  console.log(`Created admin ${email}. Sign in and change the password.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
