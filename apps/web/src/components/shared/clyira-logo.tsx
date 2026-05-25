export function ClyiraLogo({ className = "w-10 h-10" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      fill="none"
      className={className}
    >
      <defs>
        <radialGradient id="__clyira_node_grad__" cx="38%" cy="38%" r="62%">
          <stop offset="0%" stopColor="#f0ecff" />
          <stop offset="45%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#7654c9" />
        </radialGradient>
      </defs>

      {/* Outer rounded frame — gap at top-right where connector exits */}
      <path
        d="M 68 10 Q 10 10 10 32 L 10 70 Q 10 90 30 90 L 70 90 Q 90 90 90 70 L 90 44"
        stroke="#7654c9"
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Inner C arc */}
      <path
        d="M 67 35 A 20 20 0 1 0 67 65"
        stroke="#7654c9"
        strokeWidth="9"
        strokeLinecap="round"
      />

      {/* Thin connector line from frame end to node */}
      <line
        x1="90"
        y1="44"
        x2="80"
        y2="17"
        stroke="#7654c9"
        strokeWidth="4.5"
        strokeLinecap="round"
      />

      {/* Glowing node */}
      <circle
        cx="80"
        cy="14"
        r="10"
        fill="url(#__clyira_node_grad__)"
        style={{
          filter:
            "drop-shadow(0 0 4px rgba(167, 139, 250, 0.95)) drop-shadow(0 0 10px rgba(118, 84, 201, 0.55))",
        }}
      />
    </svg>
  );
}
