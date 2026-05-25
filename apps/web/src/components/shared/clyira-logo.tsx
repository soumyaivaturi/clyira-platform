export function ClyiraLogo({ className = "w-10 h-10" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      fill="none"
      className={className}
    >
      {/* Outer rounded frame — gap at top-right where node sits */}
      <path
        d="M 68 8 Q 10 8 10 30 L 10 70 Q 10 92 32 92 L 70 92 Q 92 92 92 70 L 92 46"
        stroke="#7654c9"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Inner C arc */}
      <path
        d="M 68 34 A 22 22 0 1 0 68 66"
        stroke="#7654c9"
        strokeWidth="10"
        strokeLinecap="round"
      />
      {/* Connector line from frame end to dot */}
      <line
        x1="92"
        y1="46"
        x2="80"
        y2="34"
        stroke="#7654c9"
        strokeWidth="8"
        strokeLinecap="round"
      />
      {/* Node dot */}
      <circle cx="80" cy="34" r="7" fill="#7654c9" />
    </svg>
  );
}
