"use client";

import Link from "next/link";
import type { DecisionMeta } from "@/lib/api";
import { getDecisionMeta } from "@/lib/decisions";

interface DecisionGridProps {
  decisions: DecisionMeta[];
}

export default function DecisionGrid({ decisions }: DecisionGridProps) {
  return (
    <div className="grid grid-cols-2 gap-px mx-4" style={{ background: "rgba(255,255,255,0.04)" }}>
      {decisions.map((decision, index) => {
        const meta = getDecisionMeta(decision.decision_type);
        return (
          <Link
            key={decision.decision_type}
            href={`/decide/${decision.decision_type}`}
            className="glass interactive-panel fade-up block px-5 py-5 hover:bg-white/5"
            style={{ animationDelay: `${index * 70}ms` }}
          >
            <p className={`text-[10px] font-mono font-bold uppercase tracking-widest mb-3 ${meta.color}`}>
              {meta.abbr}
            </p>
            <h3 className="font-bold text-sm text-white leading-snug mb-1">
              {decision.display_name}
            </h3>
            <p className="text-gray-500 text-xs leading-snug">
              {decision.description}
            </p>
          </Link>
        );
      })}
    </div>
  );
}
