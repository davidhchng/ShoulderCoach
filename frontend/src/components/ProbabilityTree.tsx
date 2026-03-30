"use client";

// Probability tree for three_vs_two (down 2)
// Shows the branching math: take 3 vs take 2 → OT
interface Props {
  threeMakePct: number;   // e.g. 34.8
  twoMakePct: number;     // e.g. 60.0
  otWinRate: number;      // e.g. 50.0
  pWinGo3: number;        // computed win % going for 3
  pWinGo2: number;        // computed win % going for 2+OT
}

function Row({ label, pct, color, sub }: { label: string; pct: number; color: string; sub?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-1 self-stretch" style={{ backgroundColor: color }} />
      <div className="flex-1">
        <div className="flex justify-between items-baseline">
          <span className="text-[10px] uppercase tracking-widest text-gray-500">{label}</span>
          <span className="text-sm font-black tabular-nums text-white">{pct.toFixed(1)}%</span>
        </div>
        {sub && <p className="text-[9px] text-gray-700 mt-0.5">{sub}</p>}
        <div className="h-1 bg-[#1e1e1e] mt-1.5 overflow-hidden">
          <div className="h-full transition-all duration-700" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }} />
        </div>
      </div>
    </div>
  );
}

export default function ProbabilityTree({ threeMakePct, twoMakePct, otWinRate, pWinGo3, pWinGo2 }: Props) {
  const winner = pWinGo3 >= pWinGo2 ? "3" : "2";

  return (
    <div className="space-y-0">
      {/* Go for 3 branch */}
      <div className="border border-[#1e1e1e] px-4 py-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[9px] font-mono uppercase tracking-widest text-gray-600">Option A — Go for 3</p>
          {winner === "3" && (
            <span className="text-[9px] font-mono uppercase tracking-widest text-orange-500 border border-orange-800 px-2 py-0.5">
              Recommended
            </span>
          )}
        </div>
        <div className="space-y-2.5">
          <Row
            label={`Make 3 → win outright`}
            pct={threeMakePct}
            color="#f97316"
            sub={`${threeMakePct.toFixed(1)}% historical 3pt make rate here`}
          />
          <Row
            label="Miss → lose"
            pct={100 - threeMakePct}
            color="#333"
          />
        </div>
        <div className="mt-3 pt-3 border-t border-[#1a1a1a] flex justify-between items-baseline">
          <span className="text-[9px] uppercase tracking-widest text-gray-600">Net win probability</span>
          <span className="text-base font-black text-white tabular-nums">{pWinGo3.toFixed(1)}%</span>
        </div>
      </div>

      {/* Go for 2 branch */}
      <div className="border border-[#1e1e1e] px-4 py-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[9px] font-mono uppercase tracking-widest text-gray-600">Option B — Play for 2 + OT</p>
          {winner === "2" && (
            <span className="text-[9px] font-mono uppercase tracking-widest text-orange-500 border border-orange-800 px-2 py-0.5">
              Recommended
            </span>
          )}
        </div>
        <div className="space-y-2.5">
          <Row
            label={`Make 2 → overtime`}
            pct={twoMakePct}
            color="#eab308"
            sub={`then ${otWinRate.toFixed(0)}% OT win rate`}
          />
          <Row
            label="Win in OT"
            pct={twoMakePct * (otWinRate / 100)}
            color="#f97316"
            sub={`${twoMakePct.toFixed(1)}% × ${otWinRate.toFixed(0)}% = net`}
          />
          <Row
            label="Miss or lose OT"
            pct={100 - (twoMakePct * (otWinRate / 100))}
            color="#333"
          />
        </div>
        <div className="mt-3 pt-3 border-t border-[#1a1a1a] flex justify-between items-baseline">
          <span className="text-[9px] uppercase tracking-widest text-gray-600">Net win probability</span>
          <span className="text-base font-black text-white tabular-nums">{pWinGo2.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}
