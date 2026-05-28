/* eslint-disable @next/next/no-img-element */
export function ClyiraLogo({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <img
      src="/clyira-logo.png"
      alt="CLYIRA.AI"
      className={className}
      style={{ mixBlendMode: "multiply" }}
    />
  );
}
