/* eslint-disable @next/next/no-img-element */
export function ClyiraLogo({ className = "h-8 w-auto", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <img
      src="/clyira-logo.png"
      alt="CLYIRA.AI"
      className={className}
      style={{ mixBlendMode: "multiply", ...style }}
    />
  );
}
