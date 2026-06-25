import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keepa — подбор товаров и сорсинг",
  description:
    "Поиск товаров Amazon, расчёт сорсинга в Китае, отчёты по категориям для команды.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
