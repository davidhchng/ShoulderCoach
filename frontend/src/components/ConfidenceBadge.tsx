interface ConfidenceBadgeProps {
  n: number;
}

export default function ConfidenceBadge({ n }: ConfidenceBadgeProps) {
  if (n >= 200) return <span className="text-[10px] font-medium text-green-500 uppercase tracking-widest">Strong</span>;
  if (n >= 50)  return <span className="text-[10px] font-medium text-blue-400 uppercase tracking-widest">Moderate</span>;
  if (n >= 30)  return <span className="text-[10px] font-medium text-yellow-500 uppercase tracking-widest">Limited</span>;
  return             <span className="text-[10px] font-medium text-red-400 uppercase tracking-widest">Low</span>;
}
