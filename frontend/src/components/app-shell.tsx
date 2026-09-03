import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Command } from "cmdk";
import {
  AlertOctagon,
  Bell,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  History as HistoryIcon,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Moon,
  Search,
  Settings as SettingsIcon,
  Sparkles,
  Sun,
  User,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-store";
import { useTheme } from "@/lib/theme-store";
import { Button } from "@/components/ui/button";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", icon: AlertOctagon },
  { to: "/investigate", label: "Investigation", icon: Sparkles },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/history", label: "History", icon: HistoryIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
] as const;

// ─── Search palette ────────────────────────────────────────────────────────────
const searchItems = [
  {
    label: "Dashboard",
    to: "/dashboard",
    icon: LayoutDashboard,
    group: "Pages",
  },
  { label: "Incidents", to: "/incidents", icon: AlertOctagon, group: "Pages" },
  {
    label: "Investigation",
    to: "/investigate",
    icon: Sparkles,
    group: "Pages",
  },
  { label: "Documents", to: "/documents", icon: FileText, group: "Pages" },
  { label: "Chat", to: "/chat", icon: MessageSquare, group: "Pages" },
  { label: "History", to: "/history", icon: HistoryIcon, group: "Pages" },
  { label: "Settings", to: "/settings", icon: SettingsIcon, group: "Pages" },
];

function SearchPalette({
  onClose,
  open,
}: {
  onClose: () => void;
  open: boolean;
}) {
  const navigate = useNavigate();

  const runCommand = useCallback(
    (command: () => unknown) => {
      onClose();
      command();
    },
    [onClose],
  );

  return (
    <Command.Dialog
      open={open}
      onOpenChange={(isOpen) => !isOpen && onClose()}
      label="Global Command Menu"
      className="fixed left-1/2 top-1/2 z-50 w-full max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-border bg-card shadow-2xl animate-in fade-in zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out data-[state=closed]:zoom-out-95"
    >
      <div className="flex items-center border-b border-border px-4 py-3">
        <Search className="mr-3 h-4 w-4 shrink-0 opacity-50" />
        <Command.Input
          placeholder="Search pages, features..."
          className="flex h-10 w-full rounded-md bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <Command.List className="max-h-80 overflow-y-auto p-2">
        <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
          No results found.
        </Command.Empty>
        <Command.Group
          heading="Pages"
          className="px-2 py-1.5 text-xs font-medium text-muted-foreground"
        >
          {searchItems.map((item) => {
            const Icon = item.icon;
            return (
              <Command.Item
                key={item.to}
                onSelect={() =>
                  runCommand(() => navigate({ to: item.to as "/" }))
                }
                className="relative flex cursor-pointer select-none items-center rounded-md px-3 py-2 text-sm outline-none aria-selected:bg-card-elevated aria-selected:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 text-foreground mt-1"
              >
                <Icon className="mr-3 h-4 w-4 text-muted-foreground" />
                <span>{item.label}</span>
              </Command.Item>
            );
          })}
        </Command.Group>
      </Command.List>
      <div className="border-t border-border px-4 py-2 flex gap-3 text-[10px] text-muted-foreground">
        <span>
          <kbd className="rounded border border-border px-1">↵</kbd> select
        </span>
        <span>
          <kbd className="rounded border border-border px-1">Esc</kbd> close
        </span>
      </div>
    </Command.Dialog>
  );
}

// ─── Notifications panel ───────────────────────────────────────────────────────
const MOCK_NOTIFICATIONS = [
  {
    id: 1,
    title: "Investigation complete",
    body: "Root cause identified for API latency spike.",
    time: "2m ago",
    read: false,
  },
  {
    id: 2,
    title: "Document indexed",
    body: "runbook.pdf has been indexed successfully.",
    time: "1h ago",
    read: false,
  },
  {
    id: 3,
    title: "Incident resolved",
    body: "Payment API incident marked as resolved.",
    time: "3h ago",
    read: true,
  },
];

function NotificationsPanel({ onClose }: { onClose: () => void }) {
  const [notifications, setNotifications] = useState(MOCK_NOTIFICATIONS);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function markAllRead() {
    setNotifications((n) => n.map((x) => ({ ...x, read: true })));
  }

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <span className="text-sm font-semibold">Notifications</span>
          <button
            onClick={markAllRead}
            className="text-xs text-primary hover:underline"
          >
            Mark all read
          </button>
        </div>
        <div className="max-h-72 overflow-auto">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={cn(
                "flex gap-3 px-4 py-3 border-b border-border last:border-0 cursor-pointer hover:bg-card-elevated/50",
                !n.read && "bg-primary/5",
              )}
              onClick={() =>
                setNotifications((prev) =>
                  prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)),
                )
              }
            >
              {!n.read && (
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
              )}
              {n.read && <span className="mt-1.5 h-2 w-2 shrink-0" />}
              <div className="min-w-0">
                <p className="text-xs font-medium">{n.title}</p>
                <p className="text-xs text-muted-foreground">{n.body}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {n.time}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ─── Profile dropdown ──────────────────────────────────────────────────────────
function ProfileDropdown({ onClose }: { onClose: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="absolute right-0 top-10 z-50 w-56 rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <p className="text-sm font-medium truncate">{user?.name}</p>
          <p className="text-xs text-muted-foreground truncate">
            {user?.email}
          </p>
          <span className="mt-1 inline-flex items-center rounded border border-border bg-card-elevated px-1.5 py-0.5 text-[10px] capitalize">
            {user?.role}
          </span>
        </div>
        <div className="p-1">
          <button
            onClick={() => {
              navigate({ to: "/settings" });
              onClose();
            }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-card-elevated"
          >
            <User className="h-3.5 w-3.5 text-muted-foreground" />
            Profile & Settings
          </button>
          <button
            onClick={() => {
              logout();
              onClose();
            }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-danger hover:bg-danger/10"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Main AppShell ─────────────────────────────────────────────────────────────
export function AppShell({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user } = useAuth();
  const { theme, toggle } = useTheme();

  const unreadCount = MOCK_NOTIFICATIONS.filter((n) => !n.read).length;

  // ⌘K / Ctrl+K to open search
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Search palette */}
      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />

      {searchOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm animate-in fade-in"
          onClick={() => setSearchOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "sticky top-0 flex h-screen flex-col border-r border-border bg-sidebar transition-[width] duration-200",
          collapsed ? "w-16" : "w-60",
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-3">
          <img src="/opslens.png" alt="OpsLens" className="h-8 w-8 shrink-0" />
          {!collapsed && (
            <div className="min-w-0">
              <span className="block text-sm font-bold tracking-tight">
                <span className="text-foreground">OPS</span>
                <span className="text-primary">LENS</span>
              </span>
              <span className="block text-[9px] tracking-widest text-muted-foreground uppercase">
                See · Analyze · Resolve
              </span>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 p-2">
          {nav.map((item, idx) => {
            const active =
              pathname === item.to ||
              (item.to !== "/dashboard" && pathname.startsWith(item.to));
            const Icon = item.icon;
            return (
              <Link
                key={idx}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/15 text-primary font-medium"
                    : "text-muted-foreground hover:bg-card-elevated/60 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="border-t border-border p-2 space-y-1">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground hover:bg-card-elevated hover:text-foreground"
          >
            {collapsed ? (
              <ChevronsRight className="h-4 w-4" />
            ) : (
              <ChevronsLeft className="h-4 w-4" />
            )}
            {!collapsed && <span>Collapse</span>}
          </button>

          <div
            className={cn(
              "flex items-center gap-2 rounded-md p-2",
              !collapsed && "bg-card-elevated",
            )}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary">
              {user?.name?.[0]?.toUpperCase() ?? "?"}
            </div>
            {!collapsed && (
              <>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium">
                    {user?.name}
                  </div>
                  <div className="text-[10px] text-muted-foreground capitalize">
                    {user?.role ?? "member"}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-6 backdrop-blur">
          <h1 className="text-sm font-semibold shrink-0">{title}</h1>

          {/* Search bar */}
          <button
            onClick={() => setSearchOpen(true)}
            className="mx-auto flex w-full max-w-sm items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:border-primary/50 hover:bg-card-elevated transition-colors"
          >
            <Search className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1 text-left">Search pages…</span>
            <kbd className="hidden sm:flex rounded border border-border bg-background px-1.5 py-0.5 text-[10px] gap-0.5 items-center">
              <span>⌘</span>
              <span>K</span>
            </kbd>
          </button>

          <div className="flex items-center gap-1 shrink-0">
            {actions}

            {/* Theme toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={toggle}
              title={
                theme === "dark"
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </Button>

            {/* Notifications */}
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => {
                  setNotifOpen((o) => !o);
                  setProfileOpen(false);
                }}
              >
                <Bell className="h-4 w-4" />
                {unreadCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                    {unreadCount}
                  </span>
                )}
              </Button>
              {notifOpen && (
                <NotificationsPanel onClose={() => setNotifOpen(false)} />
              )}
            </div>

            {/* Profile */}
            <div className="relative">
              <button
                onClick={() => {
                  setProfileOpen((o) => !o);
                  setNotifOpen(false);
                }}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary hover:ring-2 hover:ring-primary/40 transition-all"
              >
                {user?.name?.[0]?.toUpperCase() ?? "?"}
              </button>
              {profileOpen && (
                <ProfileDropdown onClose={() => setProfileOpen(false)} />
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
