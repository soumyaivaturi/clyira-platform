export function ClyiraLogo({ className = "w-10 h-10" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      fill="none"
      className={className}
    >
      <defs>
        {/* Dual-color stroke gradient: bright violet → deep indigo/blue */}
        <linearGradient
          id="__clyira_stroke_grad__"
          x1="90" y1="10" x2="10" y2="90"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#b06aff" />
          <stop offset="50%" stopColor="#7654c9" />
          <stop offset="100%" stopColor="#3730a3" />
        </linearGradient>

        {/* Connector gradient follows same palette */}
        <linearGradient
          id="__clyira_conn_grad__"
          x1="90" y1="44" x2="80" y2="17"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#7654c9" />
          <stop offset="100%" stopColor="#b06aff" />
        </linearGradient>

        {/* 3D sphere: strong specular highlight → rich violet → deep shadow */}
        <radialGradient id="__clyira_node_grad__" cx="33%" cy="30%" r="70%">
          <stop offset="0%"  stopColor="#ffffff" stopOpacity="0.98" />
          <stop offset="15%" stopColor="#ede9fe" />
          <stop offset="38%" stopColor="#b06aff" />
          <stop offset="68%" stopColor="#7654c9" />
          <stop offset="100%" stopColor="#1e1065" />
        </radialGradient>
      </defs>

      {/* Outer rounded frame — gap at top-right where connector exits */}
      <path
        d="M 68 10 Q 10 10 10 32 L 10 70 Q 10 90 30 90 L 70 90 Q 90 90 90 70 L 90 44"
        stroke="url(#__clyira_stroke_grad__)"
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ filter: "drop-shadow(0 0 2px rgba(176, 106, 255, 0.35))" }}
      />

      {/* Inner C arc */}
      <path
        d="M 67 35 A 20 20 0 1 0 67 65"
        stroke="url(#__clyira_stroke_grad__)"
        strokeWidth="9"
        strokeLinecap="round"
        style={{ filter: "drop-shadow(0 0 2px rgba(176, 106, 255, 0.35))" }}
      />

      {/* Thin connector line from frame end to node */}
      <line
        x1="90" y1="44" x2="80" y2="17"
        stroke="url(#__clyira_conn_grad__)"
        strokeWidth="4.5"
        strokeLinecap="round"
      />

      {/* Glowing 3D node */}
      <circle
        cx="80"
        cy="14"
        r="10"
        fill="url(#__clyira_node_grad__)"
        style={{
          filter:
            "drop-shadow(0 0 5px rgba(176, 106, 255, 0.95)) drop-shadow(0 0 14px rgba(118, 84, 201, 0.65)) drop-shadow(0 2px 4px rgba(30, 16, 101, 0.5))",
        }}
      />

      {/* Inner specular shine — small bright cap for 3D look */}
      <circle
        cx="76.5"
        cy="11"
        r="3.5"
        fill="white"
        fillOpacity="0.35"
      />
    </svg>
  );
}
