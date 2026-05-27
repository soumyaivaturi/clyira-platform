export function ClyiraLogo({ className = "w-10 h-10" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="-4 -4 108 108"
      fill="none"
      className={className}
    >
      <defs>
        {/* Top-bright → bottom-dark gradient: electric violet → deep indigo */}
        <linearGradient
          id="__clyira_stroke_grad__"
          x1="50" y1="0" x2="50" y2="100"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%"   stopColor="#8b5cf6" />
          <stop offset="55%"  stopColor="#5b21b6" />
          <stop offset="100%" stopColor="#1e1b4b" />
        </linearGradient>

        {/* 3D sphere radial gradient: bright specular → rich violet → deep shadow */}
        <radialGradient id="__clyira_sphere_grad__" cx="34%" cy="30%" r="70%">
          <stop offset="0%"   stopColor="#ddd6fe" />
          <stop offset="22%"  stopColor="#a78bfa" />
          <stop offset="55%"  stopColor="#7c3aed" />
          <stop offset="85%"  stopColor="#4c1d95" />
          <stop offset="100%" stopColor="#1e1047" />
        </radialGradient>
      </defs>

      {/* Outer rounded square frame — gap at top-right; right side = "i" stem */}
      <path
        d="M 74 8 Q 8 8 8 24 L 8 76 Q 8 92 24 92 L 76 92 Q 92 92 92 76 L 92 30"
        stroke="url(#__clyira_stroke_grad__)"
        strokeWidth="8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* "C" arc — large, centered, opening rightward */}
      <path
        d="M 65 28 A 24 24 0 1 0 65 72"
        stroke="url(#__clyira_stroke_grad__)"
        strokeWidth="8"
        strokeLinecap="round"
      />

      {/* "i" dot — 3D sphere floating above the frame's right-side top */}
      <circle
        cx="92"
        cy="12"
        r="11"
        fill="url(#__clyira_sphere_grad__)"
        style={{
          filter:
            "drop-shadow(0 0 5px rgba(139, 92, 246, 0.9)) drop-shadow(0 0 14px rgba(91, 33, 182, 0.5))",
        }}
      />
    </svg>
  );
}
