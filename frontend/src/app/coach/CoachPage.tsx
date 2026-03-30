"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { askCoach, type DecisionResponse } from "@/lib/api";
import DecisionCard from "@/components/DecisionCard";

interface Message {
  role: "coach" | "ai";
  text: string;
  decisionResult?: DecisionResponse;
  engineUsed?: string;
}

const STORAGE_KEY = "sc_coach_profile";

interface Profile {
  teamName: string;
  opponentName: string;
}

function loadProfile(): Profile {
  if (typeof window === "undefined") return { teamName: "", opponentName: "" };
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return { teamName: "", opponentName: "" };
  }
}

function saveProfile(p: Profile) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
}

export default function CoachPage() {
  const [profile, setProfile] = useState<Profile>({ teamName: "", opponentName: "" });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showProfile, setShowProfile] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setProfile(loadProfile()); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleProfileChange = (key: keyof Profile, val: string) => {
    const updated = { ...profile, [key]: val };
    setProfile(updated);
    saveProfile(updated);
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setMessages((prev) => [...prev, { role: "coach", text: q }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const res = await askCoach(q, {
        teamName: profile.teamName || undefined,
        opponentName: profile.opponentName || undefined,
        gameContext: context.trim() || undefined,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          text: res.answer,
          decisionResult: res.decision_result ?? undefined,
          engineUsed: res.engine_used ?? undefined,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <main className="min-h-screen max-w-md mx-auto flex flex-col">
      {/* Header */}
      <div className="glass-bar border-b border-white/5">
        <div className="flex items-center gap-2 px-4 pt-3">
          <Link href="/app" className="text-[9px] font-mono uppercase tracking-widest text-gray-500 hover:text-gray-300 transition-colors">
            ShoulderCoach
          </Link>
          <span className="text-white/20 text-[9px]">/</span>
          <span className="text-[9px] font-mono uppercase tracking-widest text-orange-400">Ask</span>
        </div>
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-4">
            <Link href="/app" className="text-gray-500 hover:text-white transition-all min-h-[44px] flex items-center text-lg">
              ←
            </Link>
            <div>
              <h1 className="text-lg font-black uppercase tracking-tight text-white leading-tight">Ask the Coach</h1>
              {(profile.teamName || profile.opponentName) && (
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mt-0.5">
                  {profile.teamName || "My Team"}{profile.opponentName ? ` vs ${profile.opponentName}` : ""}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => setShowProfile((s) => !s)}
            className="glass interactive-panel text-[9px] font-mono uppercase tracking-widest text-gray-400 hover:text-white border border-white/10 hover:border-white/20 px-3 py-2"
          >
            {showProfile ? "Done" : "Setup"}
          </button>
        </div>
      </div>

      {/* Team setup panel */}
      {showProfile && (
        <div className="glass-bar border-b border-white/5 px-4 py-4 space-y-3">
          <p className="text-[9px] font-mono uppercase tracking-widest text-gray-500 mb-3">Team Context — saved locally</p>
          <div>
            <label className="text-[9px] uppercase tracking-widest text-gray-500 block mb-1">Your Team</label>
            <input type="text" placeholder="e.g. Lakers" value={profile.teamName}
              onChange={(e) => handleProfileChange("teamName", e.target.value)}
              className="w-full glass border border-white/8 px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-white/20 bg-transparent" />
          </div>
          <div>
            <label className="text-[9px] uppercase tracking-widest text-gray-500 block mb-1">Opponent</label>
            <input type="text" placeholder="e.g. Celtics" value={profile.opponentName}
              onChange={(e) => handleProfileChange("opponentName", e.target.value)}
              className="w-full glass border border-white/8 px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-white/20 bg-transparent" />
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {isEmpty && !loading && (
          <div className="pt-8 space-y-6">
            <p className="text-[10px] uppercase tracking-widest text-gray-600 text-center">
              Ask anything — I&apos;ll pull from the data when I can
            </p>
            <div className="space-y-2">
              {[
                "Should I foul when up 3 with 8 seconds left?",
                "They just went on a 7-0 run in the 4th. Should I call timeout?",
                "My center shoots 45% from the line. Is hack-a-player worth it?",
                "We're down 2 with 20 seconds left. Go for 3 or play for OT?",
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInput(prompt)}
                  className="interactive-panel w-full text-left px-4 py-3 glass border border-white/8 text-gray-400 text-xs hover:border-white/20 hover:text-gray-200"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col ${msg.role === "coach" ? "items-end" : "items-start"}`}>
            {/* Text bubble */}
            <div className={`max-w-[88%] px-4 py-3 text-sm leading-relaxed ${
              msg.role === "coach"
                ? "bg-orange-500/90 backdrop-blur-sm text-white"
                : "glass border border-white/8 text-gray-200"
            }`}>
              {msg.role === "ai" && (
                <div className="flex items-center gap-2 mb-1.5">
                  <p className="text-[9px] font-mono uppercase tracking-widest text-gray-600">ShoulderCoach</p>
                  {msg.engineUsed && (
                    <span className="text-[9px] font-mono uppercase tracking-widest text-orange-500 border border-orange-900 px-1.5 py-0.5">
                      {msg.engineUsed.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
              )}
              {msg.text}
            </div>

            {/* Inline decision card when engine ran */}
            {msg.role === "ai" && msg.decisionResult && (
              <div className="w-full mt-2">
                <DecisionCard result={msg.decisionResult} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="glass border border-white/8 px-4 py-3">
              <p className="text-[9px] font-mono uppercase tracking-widest text-gray-600 mb-1.5">ShoulderCoach</p>
              <div className="flex gap-1.5 items-center h-4">
                <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && <div className="border border-red-900 px-4 py-3 text-red-400 text-sm">{error}</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="glass-bar border-t border-white/5 px-4 py-3 space-y-2">
        <input type="text"
          placeholder="Game situation (optional) — e.g. Q4, down 2, 30s left"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          className="w-full bg-transparent border-b border-white/8 px-0 py-1.5 text-[11px] text-gray-400 placeholder-gray-600 focus:outline-none focus:border-white/20 transition-colors" />
        <div className="flex gap-2">
          <input type="text"
            placeholder="Ask a coaching question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            className="flex-1 glass border border-white/8 px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-white/20 min-h-[44px] bg-transparent" />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="interactive-panel px-4 bg-orange-500 hover:bg-orange-400 text-white font-black text-xs uppercase tracking-widest disabled:opacity-30 disabled:cursor-not-allowed min-h-[44px] whitespace-nowrap shadow-[0_12px_30px_rgba(249,115,22,0.28)]"
          >
            Ask
          </button>
        </div>
      </div>
    </main>
  );
}
