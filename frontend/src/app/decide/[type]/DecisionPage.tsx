"use client";

import { useState } from "react";
import Link from "next/link";
import type { DecisionMeta, DecisionResponse } from "@/lib/api";
import { postDecision, parseDecisionInputs } from "@/lib/api";
import InputField from "@/components/InputField";
import DecisionCard from "@/components/DecisionCard";
import { getDecisionMeta } from "@/lib/decisions";

interface DecisionPageProps {
  meta: DecisionMeta;
}

function buildDefaultInputs(meta: DecisionMeta): Record<string, string | boolean | number> {
  const defaults: Record<string, string | boolean | number> = {};
  for (const field of meta.input_schema.fields) {
    defaults[field.key] = field.default;
  }
  return defaults;
}

export default function DecisionPage({ meta }: DecisionPageProps) {
  const decisionMeta = getDecisionMeta(meta.decision_type);
  const [inputs, setInputs] = useState<Record<string, string | boolean | number>>(
    buildDefaultInputs(meta)
  );
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");

  const handleChange = (key: string, value: string | boolean | number) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
    setResult(null);
    setError(null);
  };

  const handleParse = async () => {
    if (!description.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const { inputs: parsed } = await parseDecisionInputs(meta.decision_type, description);
      setInputs((prev) => ({
        ...prev,
        ...(parsed as Record<string, string | boolean | number>),
      }));
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse situation");
    } finally {
      setParsing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await postDecision(meta.decision_type, inputs);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen max-w-md mx-auto">
      {/* Header bar */}
      <div className="border-b border-[#141414]">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 px-4 pt-3 pb-0">
          <Link
            href="/"
            className="text-[9px] font-mono uppercase tracking-widest text-gray-600 hover:text-gray-400 transition-colors"
          >
            ShoulderCoach
          </Link>
          <span className="text-gray-700 text-[9px]">/</span>
          <span className={`text-[9px] font-mono uppercase tracking-widest ${decisionMeta.color}`}>
            {decisionMeta.abbr}
          </span>
        </div>
        <div className="flex items-center gap-4 px-4 py-3">
          <Link
            href="/"
            className="text-gray-600 hover:text-white transition-colors min-h-[44px] flex items-center text-lg"
          >
            ←
          </Link>
          <h1 className="text-lg font-black uppercase tracking-tight text-white leading-tight">
            {meta.display_name}
          </h1>
        </div>
      </div>

      <div className="px-4 py-5 space-y-4">
        {/* Natural language input */}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Describe the situation..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleParse()}
            className="flex-1 bg-[#0f0f0f] border border-[#1e1e1e] px-4 py-3
                       text-white text-sm placeholder-gray-700
                       focus:outline-none focus:border-[#333]
                       min-h-[44px]"
          />
          <button
            type="button"
            onClick={handleParse}
            disabled={parsing || !description.trim()}
            className="px-4 border border-[#1e1e1e] text-gray-500 hover:text-white hover:border-[#333]
                       transition-colors disabled:opacity-30 disabled:cursor-not-allowed
                       text-xs uppercase tracking-widest font-medium min-h-[44px] whitespace-nowrap"
          >
            {parsing ? "..." : "Fill"}
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="border border-[#1e1e1e] px-4 py-5 mb-3">
            {meta.input_schema.fields.map((field) => (
              <InputField
                key={field.key}
                field={field}
                value={inputs[field.key] ?? field.default}
                onChange={(val) => handleChange(field.key, val)}
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 bg-orange-500 hover:bg-orange-400 active:bg-orange-600
                       text-white font-black text-base uppercase tracking-widest
                       transition-colors duration-100
                       disabled:opacity-50 disabled:cursor-not-allowed
                       min-h-[52px]"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Analyzing
              </span>
            ) : (
              "Get Call"
            )}
          </button>
        </form>

        {/* Error */}
        {error && (
          <div className="border border-red-900 px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Result */}
        {result && <DecisionCard result={result} />}
      </div>
    </main>
  );
}
