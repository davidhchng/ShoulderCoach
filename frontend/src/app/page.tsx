import Link from "next/link";
import { fetchDecisions, type DecisionMeta } from "@/lib/api";
import DecisionGrid from "@/components/DecisionGrid";
import Basketball from "@/components/Basketball";

export default async function HomePage() {
  let decisions: DecisionMeta[] = [];
  let error: string | null = null;

  try {
    decisions = await fetchDecisions();
  } catch {
    error = "Backend offline — start uvicorn and reload.";
  }

  return (
    <main className="min-h-screen max-w-md mx-auto flex flex-col">
      {/* Hero */}
      <div className="relative overflow-hidden px-5 pt-12 pb-8 border-b border-[#141414]">
        {/* Basketball — large, partially offscreen right */}
        <div className="absolute right-[-28px] top-1/2 -translate-y-1/2 pointer-events-none">
          <Basketball size={190} className="opacity-90" />
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-[200px]">
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.22em] text-orange-500 mb-4">
            In-Game · Basketball
          </p>
          <h1 className="text-[42px] font-black uppercase leading-[0.92] tracking-tight text-white mb-4">
            Shoulder<br />Coach
          </h1>
          <p className="text-xs text-gray-500 leading-relaxed">
            Real-time decisions backed by 5 seasons of NBA play-by-play data.
          </p>
        </div>

        {/* Stat bar */}
        <div className="relative z-10 flex gap-5 mt-7">
          <div>
            <p className="text-base font-black text-white tabular-nums leading-none">5</p>
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">Seasons</p>
          </div>
          <div className="w-px bg-[#1e1e1e]" />
          <div>
            <p className="text-base font-black text-white tabular-nums leading-none">8</p>
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">Decisions</p>
          </div>
          <div className="w-px bg-[#1e1e1e]" />
          <div>
            <p className="text-base font-black text-white tabular-nums leading-none">5K+</p>
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">Games</p>
          </div>
        </div>
      </div>

      {/* Ask the Coach card */}
      <Link
        href="/coach"
        className="mx-5 mt-5 flex items-center justify-between border border-[#1e1e1e] px-4 py-4 hover:border-[#333] hover:bg-[#0d0d0d] transition-colors group"
      >
        <div>
          <p className="text-[9px] font-mono uppercase tracking-widest text-orange-500 mb-1">
            Custom
          </p>
          <p className="text-sm font-bold text-white">Ask the Coach</p>
          <p className="text-xs text-gray-600 mt-0.5">
            Any situation, any question
          </p>
        </div>
        <span className="text-gray-600 group-hover:text-white transition-colors text-lg">→</span>
      </Link>

      {/* Section label */}
      <div className="px-5 pt-5 pb-3 flex items-center gap-3">
        <p className="text-[9px] font-mono font-bold uppercase tracking-[0.22em] text-gray-600">
          Make a Call
        </p>
        <div className="flex-1 h-px bg-[#141414]" />
      </div>

      {/* Error or grid */}
      {error ? (
        <div className="mx-5 border border-red-900 px-4 py-3 text-red-400 text-sm">
          {error}
        </div>
      ) : (
        <DecisionGrid decisions={decisions} />
      )}

      {/* Footer */}
      <div className="mt-auto px-5 py-6 border-t border-[#141414]">
        <p className="text-[9px] uppercase tracking-widest text-gray-700 text-center">
          ShoulderCoach · NBA 2019–2024
        </p>
      </div>
    </main>
  );
}
