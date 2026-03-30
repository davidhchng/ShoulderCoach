"use client";

interface StatArcProps {
  value: number;   // 0–100
  color?: string;  // stroke color
  size?: number;
}

export default function StatArc({ value, color = "#f97316", size = 120 }: StatArcProps) {
  const r = 46;
  const cx = 60;
  const cy = 60;
  // Arc spans 220 degrees (from 160deg to 20deg going clockwise)
  const arcDeg = 220;
  const circumference = 2 * Math.PI * r;
  const arcLen = (arcDeg / 360) * circumference;
  const gap = circumference - arcLen;
  // Fill proportion
  const filled = (Math.min(Math.max(value, 0), 100) / 100) * arcLen;
  const offset = arcLen - filled;

  // Start angle: 160deg from positive x-axis (bottom-left)
  const startDeg = 160;
  const startRad = (startDeg * Math.PI) / 180;
  const sx = cx + r * Math.cos(startRad);
  const sy = cy + r * Math.sin(startRad);

  // Describe the arc path
  const endDeg = startDeg + arcDeg;
  const endRad = (endDeg * Math.PI) / 180;
  const ex = cx + r * Math.cos(endRad);
  const ey = cy + r * Math.sin(endRad);

  const trackPath = `M ${sx} ${sy} A ${r} ${r} 0 1 1 ${ex} ${ey}`;
  const fillPath = trackPath;

  return (
    <svg width={size} height={size} viewBox="0 0 120 120">
      {/* Track */}
      <path
        d={trackPath}
        className="arc-track"
        strokeWidth={6}
      />
      {/* Fill */}
      <path
        d={fillPath}
        className="arc-fill"
        stroke={color}
        strokeWidth={6}
        strokeDasharray={`${arcLen} ${gap}`}
        strokeDashoffset={offset}
      />
    </svg>
  );
}
