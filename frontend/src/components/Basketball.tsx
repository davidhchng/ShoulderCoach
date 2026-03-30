export default function Basketball({ size = 120, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="ballGrad" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#fb923c" />
          <stop offset="60%" stopColor="#ea580c" />
          <stop offset="100%" stopColor="#9a3412" />
        </radialGradient>
      </defs>
      {/* Ball */}
      <circle cx="60" cy="60" r="56" fill="url(#ballGrad)" />
      {/* Seam shadow/depth */}
      <circle cx="60" cy="60" r="56" fill="none" stroke="#7c2d12" strokeWidth="0.5" opacity="0.4" />
      {/* Left vertical seam */}
      <path
        d="M60 4 C44 22 38 41 38 60 C38 79 44 98 60 116"
        stroke="#7c2d12"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      {/* Right vertical seam */}
      <path
        d="M60 4 C76 22 82 41 82 60 C82 79 76 98 60 116"
        stroke="#7c2d12"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      {/* Top horizontal seam */}
      <path
        d="M4 60 C22 44 41 38 60 38 C79 38 98 44 116 60"
        stroke="#7c2d12"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      {/* Bottom horizontal seam */}
      <path
        d="M4 60 C22 76 41 82 60 82 C79 82 98 76 116 60"
        stroke="#7c2d12"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      {/* Highlight */}
      <ellipse cx="42" cy="38" rx="10" ry="6" fill="white" opacity="0.12" transform="rotate(-35 42 38)" />
    </svg>
  );
}
