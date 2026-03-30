import Link from "next/link";
import { fetchDecisions, type DecisionMeta } from "@/lib/api";
import DecisionGrid from "@/components/DecisionGrid";

export default async function AppHomePage() {
  let decisions: DecisionMeta[] = [];
  let error: string | null = null;

  try {
    decisions = await fetchDecisions();
  } catch {
    error = "Backend offline. Start uvicorn and reload.";
  }

  return (
    <main className="min-h-screen max-w-md mx-auto flex flex-col">
      <div className="glass-bar relative overflow-hidden px-5 pt-12 pb-8 border-b border-white/5">
        <div className="relative z-10 mb-1">
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.22em] text-orange-400 mb-4">
            In-Game · Basketball
          </p>
          <h1 className="text-[48px] font-black uppercase leading-[0.88] tracking-tight text-white mb-4">
            Shoulder
            <br />
            Coach
          </h1>
          <p className="text-xs text-gray-400 leading-relaxed max-w-[220px]">
            Real-time decisions backed by 5 seasons of NBA play-by-play data.
          </p>
        </div>

        <div className="relative z-10 flex gap-5 mt-7">
          {[["5", "Seasons"], ["8", "Decisions"], ["5K+", "Games"]].map(([val, label], i, arr) => (
            <div key={label} className="flex items-center gap-5">
              <div>
                <p className="text-base font-black text-white tabular-nums leading-none">{val}</p>
                <p className="text-[9px] uppercase tracking-widest text-gray-500 mt-0.5">{label}</p>
              </div>
              {i < arr.length - 1 && <div className="w-px h-6 bg-white/10" />}
            </div>
          ))}
        </div>
      </div>

      <Link
        href="/coach"
        className="glass interactive-panel fade-up mx-4 mt-4 flex items-center justify-between border border-white/8 px-4 py-4 hover:border-white/15 hover:bg-white/5 group"
        style={{ animationDelay: "120ms" }}
      >
        <div>
          <p className="text-[9px] font-mono uppercase tracking-widest text-orange-400 mb-1">Custom</p>
          <p className="text-sm font-bold text-white">Ask the Coach</p>
          <p className="text-xs text-gray-500 mt-0.5">Any situation, any question</p>
        </div>
        <span className="text-gray-500 group-hover:text-white transition-colors text-lg">→</span>
      </Link>

      <div className="px-5 pt-5 pb-3 flex items-center gap-3">
        <p className="text-[9px] font-mono font-bold uppercase tracking-[0.22em] text-gray-500">
          Make a Call
        </p>
        <div className="flex-1 h-px bg-white/6" />
      </div>

      {error ? (
        <div className="mx-4 glass border border-red-900/50 px-4 py-3 text-red-400 text-sm">{error}</div>
      ) : (
        <DecisionGrid decisions={decisions} />
      )}

      <div className="mt-auto px-5 py-6 border-t border-white/5">
        <p className="text-[9px] uppercase tracking-widest text-gray-600 text-center">
          ShoulderCoach · NBA 2019–2024
        </p>
      </div>
    </main>
  );
}
