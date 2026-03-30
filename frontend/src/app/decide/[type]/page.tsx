import { fetchDecisions } from "@/lib/api";
import DecisionPage from "./DecisionPage";

export default async function Page(props: PageProps<"/decide/[type]">) {
  const { type } = await props.params;
  const decisions = await fetchDecisions().catch(() => []);
  const meta = decisions.find((d) => d.decision_type === type);

  if (!meta) {
    return (
      <main className="min-h-screen px-4 py-8 max-w-md mx-auto flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-400 text-lg">Decision type not found: {type}</p>
          <a href="/" className="text-orange-400 text-sm mt-3 block">
            ← Back to home
          </a>
        </div>
      </main>
    );
  }

  return <DecisionPage meta={meta} />;
}
