import Link from "next/link";

const features = [
  {
    label: "Live Calls",
    title: "Eight late-game decision tools",
    text: "Get a fast recommendation for common coaching moments like fouling up three, timeout timing, or choosing between a quick two and a three.",
  },
  {
    label: "Grounded",
    title: "Backed by historical NBA data",
    text: "Each result shows the confidence, comparison edge, and supporting numbers so the recommendation feels usable instead of vague.",
  },
  {
    label: "Flexible",
    title: "Ask your own coaching question",
    text: "Use the coach flow when the situation is messy and you want the app to interpret the context for you.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen max-w-md mx-auto flex flex-col px-4 py-5">
      <section className="glass-bar fade-up relative overflow-hidden border border-white/8 px-5 pt-12 pb-8">
        <p className="text-[9px] font-mono font-bold uppercase tracking-[0.22em] text-orange-400 mb-4">
          Basketball Decision Support
        </p>
        <h1 className="text-[52px] font-black uppercase leading-[0.86] tracking-tight text-white">
          Shoulder
          <br />
          Coach
        </h1>
        <p className="mt-4 max-w-[260px] text-sm leading-relaxed text-gray-300">
          A coaching assistant for in-game basketball decisions. It turns historical NBA data into fast calls you can actually use on the sideline.
        </p>

        <div className="mt-8 space-y-3">
          <Link
            href="/app"
            className="interactive-panel block w-full bg-orange-500 hover:bg-orange-400 text-white font-black text-sm uppercase tracking-[0.18em] text-center px-4 py-4 shadow-[0_16px_36px_rgba(249,115,22,0.3)]"
          >
            Enter App
          </Link>
          <Link
            href="/coach"
            className="glass interactive-panel block w-full border border-white/10 px-4 py-4 text-center text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-gray-300 hover:text-white hover:border-white/20"
          >
            Or Go Straight To Ask The Coach
          </Link>
        </div>
      </section>

      <section className="pt-4 space-y-px">
        {features.map((feature, index) => (
          <div
            key={feature.title}
            className="glass fade-up border border-white/8 px-4 py-4"
            style={{ animationDelay: `${120 + index * 90}ms` }}
          >
            <p className="text-[9px] font-mono uppercase tracking-[0.22em] text-orange-400 mb-2">
              {feature.label}
            </p>
            <h2 className="text-base font-black text-white leading-tight">{feature.title}</h2>
            <p className="mt-2 text-xs leading-relaxed text-gray-400">{feature.text}</p>
          </div>
        ))}
      </section>

      <section className="fade-up pt-4" style={{ animationDelay: "380ms" }}>
        <div className="glass border border-white/8 px-4 py-4">
          <div className="flex items-center gap-3 mb-3">
            <p className="text-[9px] font-mono uppercase tracking-[0.22em] text-gray-500">How It Works</p>
            <div className="flex-1 h-px bg-white/6" />
          </div>
          <div className="grid grid-cols-3 gap-px" style={{ background: "rgba(255,255,255,0.04)" }}>
            {[
              ["1", "Pick", "Open a decision tool"],
              ["2", "Input", "Describe the situation"],
              ["3", "Decide", "Use the recommendation"],
            ].map(([step, label, text], index) => (
              <div key={label} className="glass px-3 py-4">
                <p className="text-[18px] font-black text-white leading-none">{step}</p>
                <p className="text-[9px] uppercase tracking-widest text-orange-400 mt-2">{label}</p>
                <p className="text-[11px] text-gray-500 leading-relaxed mt-2">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="mt-auto pt-6 pb-2">
        <p className="text-[9px] uppercase tracking-widest text-gray-600 text-center">
          ShoulderCoach · Enter the app when you are ready
        </p>
      </div>
    </main>
  );
}
