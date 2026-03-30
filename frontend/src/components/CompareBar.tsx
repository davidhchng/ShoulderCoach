"use client";

interface CompareBarProps {
  primaryLabel: string;
  primaryValue: number;
  comparisonLabel: string;
  comparisonValue: number;
  unit?: string;
}

export default function CompareBar({
  primaryLabel,
  primaryValue,
  comparisonLabel,
  comparisonValue,
  unit = "",
}: CompareBarProps) {
  const total = primaryValue + comparisonValue;
  const primaryPct = total > 0 ? (primaryValue / total) * 100 : 50;
  const compPct = 100 - primaryPct;

  // Which side is winning?
  const primaryWins = primaryValue >= comparisonValue;

  return (
    <div className="space-y-2">
      {/* Labels row */}
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] uppercase tracking-widest text-gray-500 max-w-[45%] leading-snug">
          {primaryLabel}
        </span>
        <span className="text-[10px] uppercase tracking-widest text-gray-500 max-w-[45%] text-right leading-snug">
          {comparisonLabel}
        </span>
      </div>

      {/* Split bar */}
      <div className="h-8 flex overflow-hidden rounded-none">
        <div
          className="flex items-center justify-start pl-3 transition-all duration-700 bg-orange-500"
          style={{ width: `${primaryPct}%` }}
        >
          <span className="text-xs font-black text-white tabular-nums whitespace-nowrap">
            {primaryValue}{unit}
          </span>
        </div>
        <div
          className="flex items-center justify-end pr-3 transition-all duration-700 bg-[#222]"
          style={{ width: `${compPct}%` }}
        >
          <span className="text-xs font-bold text-gray-400 tabular-nums whitespace-nowrap">
            {comparisonValue}{unit}
          </span>
        </div>
      </div>

      {/* Edge callout */}
      {Math.abs(primaryValue - comparisonValue) > 0 && (
        <p className="text-[9px] uppercase tracking-widest text-gray-600 text-center">
          {primaryWins ? (
            <span>
              <span className="text-orange-400 font-bold">
                +{Math.abs(primaryValue - comparisonValue).toFixed(1)}{unit}
              </span>{" "}
              edge for recommended option
            </span>
          ) : (
            <span>
              <span className="text-gray-400 font-bold">
                +{Math.abs(primaryValue - comparisonValue).toFixed(1)}{unit}
              </span>{" "}
              edge for alternative
            </span>
          )}
        </p>
      )}
    </div>
  );
}
