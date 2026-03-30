"use client";

import Link from "next/link";
import type { DecisionMeta } from "@/lib/api";
import { getDecisionMeta } from "@/lib/decisions";

interface DecisionGridProps {
  decisions: DecisionMeta[];
}

export default function DecisionGrid({ decisions }: DecisionGridProps) {
  return (
    <div className="grid grid-cols-2 gap-px bg-[#141414]">
      {decisions.map((decision) => {
        const meta = getDecisionMeta(decision.decision_type);
        return (
          <Link
            key={decision.decision_type}
            href={`/decide/${decision.decision_type}`}
            className="block bg-[#080808] p-5 hover:bg-[#0f0f0f] transition-colors active:bg-[#141414]"
          >
            <p className={`text-[10px] font-mono font-bold uppercase tracking-widest mb-3 ${meta.color}`}>
              {meta.abbr}
            </p>
            <h3 className="font-bold text-sm text-white leading-snug mb-1">
              {decision.display_name}
            </h3>
            <p className="text-gray-600 text-xs leading-snug">
              {decision.description}
            </p>
          </Link>
        );
      })}
    </div>
  );
}
