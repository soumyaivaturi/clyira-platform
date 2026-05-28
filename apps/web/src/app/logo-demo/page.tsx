/* eslint-disable @next/next/no-img-element */
export default function LogoDemoPage() {
  const sizes = [
    { label: "h-6 (24px)", cls: "h-6" },
    { label: "h-7 (28px)", cls: "h-7" },
    { label: "h-8 (32px)", cls: "h-8" },
    { label: "h-9 (36px)", cls: "h-9" },
    { label: "h-10 (40px)", cls: "h-10" },
    { label: "h-12 (48px)", cls: "h-12" },
    { label: "h-14 (56px)", cls: "h-14" },
    { label: "h-16 (64px)", cls: "h-16" },
  ];

  return (
    <div className="min-h-screen bg-white p-10 space-y-10">
      <h1 className="text-lg font-semibold text-gray-500 mb-6">Logo size preview</h1>

      {/* Nav context */}
      <section>
        <p className="text-xs text-gray-400 uppercase tracking-widest mb-3">Nav bar context (h-16 bar)</p>
        <div className="space-y-3">
          {sizes.map(({ label, cls }) => (
            <div key={cls} className="h-16 border border-gray-200 rounded-lg flex items-center px-6 gap-8">
              <img src="/clyira-logo.png" alt="CLYIRA.AI" className={`${cls} w-auto`} />
              <span className="text-xs text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Auth page context */}
      <section>
        <p className="text-xs text-gray-400 uppercase tracking-widest mb-3">Auth page context (centered)</p>
        <div className="grid grid-cols-4 gap-4">
          {["h-10", "h-12", "h-14", "h-16"].map((cls) => (
            <div key={cls} className="border border-gray-200 rounded-lg p-6 flex flex-col items-center gap-2">
              <img src="/clyira-logo.png" alt="CLYIRA.AI" className={`${cls} w-auto`} />
              <span className="text-xs text-gray-400">{cls}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Sidebar context */}
      <section>
        <p className="text-xs text-gray-400 uppercase tracking-widest mb-3">Sidebar context (w-64 panel)</p>
        <div className="space-y-3">
          {["h-6", "h-7", "h-8", "h-9", "h-10"].map((cls) => (
            <div key={cls} className="w-64 h-16 border border-gray-200 rounded-lg flex items-center px-6 gap-3">
              <img src="/clyira-logo.png" alt="CLYIRA.AI" className={`${cls} w-auto`} />
              <span className="text-xs text-gray-400">{cls}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
