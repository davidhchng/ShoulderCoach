"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { analyzeShootingForm, type FormCheckResponse, type FormMetric } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function scoreColor(passing: number, total: number): string {
  if (total === 0) return "text-gray-500";
  const ratio = passing / total;
  if (ratio >= 0.8) return "text-orange-400";
  if (ratio >= 0.6) return "text-yellow-400";
  return "text-gray-400";
}

function MetricRow({ metric }: { metric: FormMetric }) {
  const hasValue = metric.value !== null;
  const inRange = metric.in_range;
  const dotColor = !hasValue ? "bg-gray-700"
    : inRange === true ? "bg-orange-400"
    : inRange === false ? "bg-gray-500"
    : "bg-gray-700";

  return (
    <div className="flex items-start gap-3 py-3 border-b border-white/5 last:border-0">
      <div className="flex-shrink-0 mt-1.5">
        <div className={`w-2 h-2 rounded-full ${dotColor}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">{metric.name}</p>
          <div className="flex items-baseline gap-1.5 flex-shrink-0">
            <span className={`text-sm font-black tabular-nums ${hasValue ? "text-white" : "text-gray-600"}`}>
              {hasValue ? `${metric.value}${metric.unit}` : "—"}
            </span>
            <span className="text-[9px] text-gray-600">ref {metric.ideal_range}</span>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 leading-snug">{metric.note}</p>
      </div>
    </div>
  );
}

export default function FormCheckPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FormCheckResponse | null>(null);

  const handleFile = (f: File) => { setFile(f); setResult(null); setError(null); };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleSubmit = async () => {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await analyzeShootingForm(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFile(null); setResult(null); setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <main className="min-h-screen max-w-md mx-auto">
      {/* Header */}
      <div className="glass-bar border-b border-white/5">
        <div className="flex items-center gap-2 px-4 pt-3 pb-0">
          <Link href="/app" className="text-[9px] font-mono uppercase tracking-widest text-gray-500 hover:text-gray-300 transition-colors">
            ShoulderCoach
          </Link>
          <span className="text-white/20 text-[9px]">/</span>
          <span className="text-[9px] font-mono uppercase tracking-widest text-orange-400">Form</span>
        </div>
        <div className="flex items-center gap-4 px-4 py-3">
          <Link href="/app" className="text-gray-500 hover:text-white transition-colors min-h-[44px] flex items-center text-lg">←</Link>
          <div>
            <h1 className="text-lg font-black uppercase tracking-tight text-white leading-tight">Shot Form Analyzer</h1>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest mt-0.5">MediaPipe Pose · 5 Metrics</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-5 space-y-4">
        {!result ? (
          <>
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`glass border-2 border-dashed cursor-pointer transition-colors px-6 py-10 text-center
                ${dragging ? "border-orange-500/60 bg-orange-500/5" : "border-white/10 hover:border-white/20"}`}
            >
              <input ref={inputRef} type="file" accept="video/*" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
              {file ? (
                <div>
                  <p className="text-white text-sm font-bold truncate">{file.name}</p>
                  <p className="text-gray-500 text-xs mt-1">{(file.size / 1024 / 1024).toFixed(1)} MB · tap to change</p>
                </div>
              ) : (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Upload Shooting Clip</p>
                  <p className="text-gray-600 text-xs">mp4, mov, avi · drag & drop or tap</p>
                </div>
              )}
            </div>

            <button
              onClick={handleSubmit}
              disabled={!file || loading}
              className="interactive-panel w-full py-4 bg-orange-500 hover:bg-orange-400 text-white font-black text-base uppercase tracking-widest disabled:opacity-40 disabled:cursor-not-allowed min-h-[52px] shadow-[0_14px_32px_rgba(249,115,22,0.28)]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Reading your form...
                </span>
              ) : "Analyze Form"}
            </button>

            {error && <div className="glass border border-red-800/50 px-4 py-3 text-red-400 text-sm">{error}</div>}

            <div className="glass border border-white/8 px-4 py-4">
              <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-3">What We Measure</p>
              <div className="space-y-1.5">
                {[
                  ["Elbow Angle", "75–110° at set point (elite ref)"],
                  ["Wrist Follow-Through", "≥3% downward snap after release"],
                  ["Shoulder Symmetry", "<6% tilt at release"],
                  ["Knee Bend", "120–165° at gather"],
                  ["Body Tilt", "≤25° lean at release"],
                ].map(([name, desc]) => (
                  <div key={name} className="flex items-baseline gap-2">
                    <span className="text-[9px] uppercase tracking-widest text-gray-600 w-28 flex-shrink-0">{name}</span>
                    <span className="text-xs text-gray-500">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Pose playback video */}
            {result.video_id && (
              <div className="glass border border-white/8 overflow-hidden soft-pop">
                <p className="text-[9px] uppercase tracking-widest text-gray-500 px-4 pt-4 pb-2">Pose Playback</p>
                <video
                  src={`${API_BASE}/api/form-check/video/${result.video_id}`}
                  autoPlay
                  loop
                  muted
                  playsInline
                  controls
                  className="w-full block h-auto"
                />
                <p className="text-[9px] text-gray-600 px-4 pb-3 pt-1 uppercase tracking-widest">
                  Skeleton overlay · phase labels · angle arcs
                </p>
              </div>
            )}

            {/* Summary bar */}
            <div className="glass border border-white/8 px-4 py-3 soft-pop flex items-center justify-between">
              <p className="text-[9px] uppercase tracking-widest text-gray-500">
                {result.frames_analyzed} frames · {result.phase_detected ? "phases detected" : "fallback phases"}
              </p>
              <p className="text-[9px] uppercase tracking-widest text-gray-600">
                {result.total > 0 ? `${result.passing}/${result.total} within ref range` : "no data"}
              </p>
            </div>

            {/* Metric rows */}
            <div className="glass border border-white/8 px-4 py-1 soft-pop">
              {result.metrics.map((m) => <MetricRow key={m.key} metric={m} />)}
            </div>

            {/* Coaching narrative */}
            {result.narrative && (
              <div className="glass border border-white/8 px-5 py-5 soft-pop">
                <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-2">Coaching Notes</p>
                <p className="text-gray-200 text-sm leading-relaxed">{result.narrative}</p>
              </div>
            )}

            <button
              onClick={reset}
              className="interactive-panel w-full py-3 glass border border-white/10 text-gray-400 hover:text-white hover:border-white/20 text-xs uppercase tracking-widest font-medium min-h-[44px]"
            >
              Check Another
            </button>
          </>
        )}
      </div>
    </main>
  );
}
