-- CreateEnum
CREATE TYPE "Role" AS ENUM ('ADMIN', 'USER');

-- CreateEnum
CREATE TYPE "ReportType" AS ENUM ('AMAZON', 'SOURCING');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT,
    "passwordHash" TEXT NOT NULL,
    "role" "Role" NOT NULL DEFAULT 'USER',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "lastLoginAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "createdById" TEXT,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "action" TEXT NOT NULL,
    "userId" TEXT,
    "userEmail" TEXT,
    "targetType" TEXT,
    "targetId" TEXT,
    "ip" TEXT,
    "detail" JSONB,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Report" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "type" "ReportType" NOT NULL DEFAULT 'AMAZON',
    "marketplace" TEXT NOT NULL DEFAULT 'US',
    "notes" TEXT,
    "query" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "createdById" TEXT NOT NULL,

    CONSTRAINT "Report_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ReportItem" (
    "id" TEXT NOT NULL,
    "reportId" TEXT NOT NULL,
    "asin" TEXT NOT NULL,
    "title" TEXT,
    "brand" TEXT,
    "manufacturer" TEXT,
    "marketplace" TEXT NOT NULL DEFAULT 'US',
    "rootCategory" TEXT,
    "categoryPath" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "imageUrl" TEXT,
    "sellPrice" DOUBLE PRECISION,
    "monthlySold" INTEGER,
    "rating" DOUBLE PRECISION,
    "reviewCount" INTEGER,
    "referralPct" DOUBLE PRECISION,
    "fbaFee" DOUBLE PRECISION,
    "landedCost" DOUBLE PRECISION,
    "marginPct" DOUBLE PRECISION,
    "roiPct" DOUBLE PRECISION,
    "verdict" TEXT,
    "confidence" TEXT,
    "rationale" TEXT,
    "data" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ReportItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SavedQuery" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" "ReportType" NOT NULL DEFAULT 'AMAZON',
    "params" JSONB NOT NULL,
    "createdById" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SavedQuery_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "KeepaCategory" (
    "catId" BIGINT NOT NULL,
    "domain" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "parentId" BIGINT,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "KeepaCategory_pkey" PRIMARY KEY ("domain","catId")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "User_role_idx" ON "User"("role");

-- CreateIndex
CREATE INDEX "AuditLog_createdAt_idx" ON "AuditLog"("createdAt");

-- CreateIndex
CREATE INDEX "AuditLog_action_idx" ON "AuditLog"("action");

-- CreateIndex
CREATE INDEX "AuditLog_userId_idx" ON "AuditLog"("userId");

-- CreateIndex
CREATE INDEX "Report_type_idx" ON "Report"("type");

-- CreateIndex
CREATE INDEX "Report_marketplace_idx" ON "Report"("marketplace");

-- CreateIndex
CREATE INDEX "Report_createdAt_idx" ON "Report"("createdAt");

-- CreateIndex
CREATE INDEX "ReportItem_reportId_idx" ON "ReportItem"("reportId");

-- CreateIndex
CREATE INDEX "ReportItem_asin_idx" ON "ReportItem"("asin");

-- CreateIndex
CREATE INDEX "ReportItem_rootCategory_idx" ON "ReportItem"("rootCategory");

-- CreateIndex
CREATE INDEX "ReportItem_verdict_idx" ON "ReportItem"("verdict");

-- CreateIndex
CREATE INDEX "KeepaCategory_domain_idx" ON "KeepaCategory"("domain");

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Report" ADD CONSTRAINT "Report_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ReportItem" ADD CONSTRAINT "ReportItem_reportId_fkey" FOREIGN KEY ("reportId") REFERENCES "Report"("id") ON DELETE CASCADE ON UPDATE CASCADE;
