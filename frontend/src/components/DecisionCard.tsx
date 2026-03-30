import type { DecisionResponse } from "@/lib/api";
import ConfidenceBadge from "./ConfidenceBadge";
import StatArc from "./StatArc";
import CompareBar from "./CompareBar";
import ProbabilityTree from "./ProbabilityTree";

interface DecisionCardProps {
  result: DecisionResponse;
}

function arcColor(confidence: string) {
  if (confidence === "high") return "#f97316";
  if (confidence === "moderate") return "#eab308";
  return "#6b7280";
}

function isPct(label: string): boolean {
  const l = label.toLowerCase();
  return l.includes("%") || l.includes("win") || l.includes("rate") || l.includes("pct");
}

function formatVal(value: number, label: string): string {
  if (isPct(label) && value <= 1) return (value * 100).toFixed(1);
  return value % 1 === 0 ? String(value) : value.toFixed(1);
}

function getDisplayValue(value: number, label: string): number {
  if (isPct(label) && value <= 1) return parseFloat((value * 100).toFixed(1));
  return parseFloat(value.toFixed(1));
}

export default function DecisionCard({ result }: DecisionCardProps) {
  if (result.insufficient_data) {
    return (
      <div className="border border-[#1e1e1e] p-6 text-center">
        <p className="text-xs uppercase tracking-widest text-gray-600 mb-2">Insufficient Data</p>
        <p className="text-gray-400 text-sm">Not enough historical situations to make a call here.</p>
      </div>
    );
  }

  const color = arcColor(result.confidence);

  const primaryDisplay = getDisplayValue(result.primary_stat, result.primary_stat_label);
  const compDisplay = result.comparison_stat !== null && result.comparison_stat !== undefined
    ? getDisplayValue(result.comparison_stat, result.comparison_stat_label ?? "")
    : null;

  const showArc = isPct(result.primary_stat_label) && primaryDisplay <= 100 && primaryDisplay >= 0;
  const unit = isPct(result.primary_stat_label) ? "%" : "";

  const hasComparison = compDisplay !== null && result.comparison_stat_label;

  return (
    <div className="space-y-px">
      {/* Low sample warning */}
      {result.low_sample_warning && (
        <div className="bg-yellow-950 border border-yellow-800/50 px-4 py-2">
          <p className="text-yellow-500 text-xs uppercase tracking-widest">
            Small sample — directional only
          </p>
        </div>
      )}

      {/* ── VERDICT ── */}
      <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-5">
        <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-2">Call</p>
        <p className="text-4xl font-black uppercase leading-none tracking-tight mb-3" style={{ color }}>
          {result.recommended_action}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[9px] font-mono uppercase tracking-widest px-2 py-0.5 border ${
            result.confidence === "high"
              ? "border-orange-800 text-orange-400"
              : result.confidence === "moderate"
              ? "border-yellow-800 text-yellow-500"
              : "border-gray-700 text-gray-500"
          }`}>
            {result.confidence} confidence
          </span>
        </div>
      </div>

      {/* ── PROBABILITY TREE (three_vs_two down 2 only) ── */}
      {result.decision_type === "three_vs_two" &&
        result.details?.three_pt_make_pct != null &&
        result.details?.two_pt_make_pct != null && (
        <div className="bg-[#0c0c0c] border border-[#1e1e1e]">
          <div className="px-5 pt-4 pb-2">
            <p className="text-[9px] uppercase tracking-widest text-gray-600">Decision Math</p>
          </div>
          <ProbabilityTree
            threeMakePct={result.details.three_pt_make_pct as number}
            twoMakePct={result.details.two_pt_make_pct as number}
            otWinRate={(result.details.ot_win_rate as number) ?? 50}
            pWinGo3={(result.details.p_win_go_for_3 as number) ?? primaryDisplay}
            pWinGo2={(result.details.p_win_go_for_2 as number) ?? (compDisplay ?? 0)}
          />
        </div>
      )}

      {/* ── HEAD-TO-HEAD VISUAL ── */}
      {hasComparison ? (
        <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-5">
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-4">Head to Head</p>
          <CompareBar
            primaryLabel={result.primary_stat_label}
            primaryValue={primaryDisplay}
            comparisonLabel={result.comparison_stat_label!}
            comparisonValue={compDisplay!}
            unit={unit}
          />
          <div className="flex justify-between mt-3">
            <p className="text-[9px] text-gray-600">
              n={result.primary_sample_size} <ConfidenceBadge n={result.primary_sample_size} />
            </p>
            {result.comparison_sample_size != null && (
              <p className="text-[9px] text-gray-600">
                n={result.comparison_sample_size} <ConfidenceBadge n={result.comparison_sample_size} />
              </p>
            )}
          </div>
        </div>
      ) : (
        /* Single stat with arc */
        <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-5 flex items-center gap-5">
          {showArc && (
            <div className="relative flex-shrink-0">
              <StatArc value={primaryDisplay} color={color} size={96} />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-black tabular-nums leading-none text-white">
                  {primaryDisplay.toFixed(1)}
                </span>
                <span className="text-[8px] text-gray-600 uppercase tracking-wide">pct</span>
              </div>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-0.5">
              {result.primary_stat_label}
            </p>
            {!showArc && (
              <p className="text-2xl font-black tabular-nums text-white">
                {formatVal(result.primary_stat, result.primary_stat_label)}
              </p>
            )}
            <p className="text-[9px] text-gray-600 mt-1">
              n={result.primary_sample_size}&nbsp;
              <ConfidenceBadge n={result.primary_sample_size} />
            </p>
          </div>
        </div>
      )}

      {/* ── EDGE ── */}
      {result.edge_pct !== null && result.edge_pct !== undefined && result.edge_pct > 0 && (
        <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-3 flex items-center gap-3">
          <div className="w-1 h-8 bg-orange-500 flex-shrink-0" />
          <div>
            <p className="text-[9px] uppercase tracking-widest text-gray-600">Edge</p>
            <p className="text-sm font-black text-white">
              <span className="text-orange-400">+{result.edge_pct}{unit}</span>
              {" "}over the alternative
            </p>
          </div>
        </div>
      )}

      {/* ── EXTRA DETAILS ── */}
      {result.details && Object.keys(result.details).filter(k => result.details[k] != null).length > 0 && (
        <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-4">
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-3">Details</p>
          <div className="space-y-2">
            {Object.entries(result.details).map(([key, val]) => {
              if (val === null || val === undefined) return null;
              return (
                <div key={key} className="flex justify-between items-baseline">
                  <span className="text-[9px] uppercase tracking-widest text-gray-600">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-gray-300 font-medium tabular-nums">{String(val)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── NARRATIVE ── */}
      {result.narrative && (
        <div className="bg-[#0c0c0c] border border-[#1e1e1e] px-5 py-4">
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-2">Analysis</p>
          <p className="text-gray-300 text-sm leading-relaxed">{result.narrative}</p>
          {!result.narrative_available && (
            <p className="text-gray-700 text-[9px] mt-2 uppercase tracking-widest">stats only</p>
          )}
        </div>
      )}
    </div>
  );
}
