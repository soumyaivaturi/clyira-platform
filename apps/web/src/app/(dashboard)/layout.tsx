"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  FileText,
  Shield,
  Radio,
  LayoutDashboard,
  Settings,
  LogOut,
  ChevronDown,
  ClipboardList,
  Layers,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { NotificationBell } from "@/components/shared/notification-bell";
import { TermsModal } from "@/components/shared/terms-modal";
import { ClyiraLogo } from "@/components/shared/clyira-logo";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes — Part 11 §11.300

const navigation = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Documents",
    href: "/documents",
    icon: FileText,
    description: "Create, assess & manage",
  },
  {
    name: "Audit Readiness",
    href: "/readiness",
    icon: Shield,
    description: "Scores, gaps & mock inspections",
  },
  {
    name: "Inspections",
    href: "/inspections",
    icon: Radio,
    description: "Real-time audit support",
  },
  {
    name: "Evidence Fabric",
    href: "/evidence",
    icon: Layers,
    description: "Import quality system data",
  },
  {
    name: "Audit Trail",
    href: "/audit",
    icon: ClipboardList,
    description: "GxP activity log",
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.push("/auth/login");
  };

  // 30-minute idle auto-logout (Part 11 §11.300)
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        logout();
        router.push("/auth/login?reason=idle");
      }, IDLE_TIMEOUT_MS);
    };
    const events = ["mousedown", "keydown", "touchstart", "scroll", "pointermove"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [logout, router]);

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : "?";

  return (
    <div className="flex h-screen">
      {/* Terms modal — shown on first login until user accepts (Part 11 §11.10(j)) */}
      {user && !user.terms_accepted_at && <TermsModal />}
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <ClyiraLogo />
            <span className="font-bold text-lg tracking-tight">
              CLYIRA<span style={{ color: "#7654c9", fontSize: "1.4em", lineHeight: 1 }}>.</span>AI
            </span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="border-t p-3">
          <Link
            href="/settings"
            className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Settings className="w-5 h-5" />
            <span>Settings</span>
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-16 border-b bg-card flex items-center justify-between px-6">
          <div />
          <div className="flex items-center gap-4">
            <NotificationBell />
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-xs font-semibold text-primary">{initials}</span>
              </div>
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium leading-none">{user?.full_name ?? "—"}</p>
                <p className="text-xs text-muted-foreground mt-0.5 capitalize">{user?.role ?? ""}</p>
              </div>
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto px-5 py-4 bg-muted/30">
          {children}
        </main>
      </div>
    </div>
  );
}
