"use client";

interface Props {
  items: string[];
  className?: string;
}

export function MarqueeStrip({ items, className = "" }: Props) {
  const doubled = [...items, ...items];

  return (
    <div className={`overflow-hidden ${className}`}>
      <div className="flex gap-12 animate-marquee whitespace-nowrap">
        {doubled.map((item, i) => (
          <span
            key={i}
            className="text-sm font-semibold text-gray-400 shrink-0 tracking-wide"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
