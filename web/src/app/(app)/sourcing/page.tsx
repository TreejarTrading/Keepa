import SourcingClient from "@/components/SourcingClient";

export const dynamic = "force-dynamic";

export default function SourcingPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Сорсинг в Китае</h1>
        <p className="text-sm text-slate-500">
          Сопоставьте товар Amazon с поставщиками (1688 / Alibaba / Made-in-China / Global Sources / DHgate),
          задайте MOQ-уровни — и получите landed-стоимость, маржу, ROI и вердикт по объёму.
        </p>
      </div>
      <SourcingClient />
    </div>
  );
}
