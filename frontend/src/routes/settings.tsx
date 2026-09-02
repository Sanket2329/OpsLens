import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-store";
import { useTheme } from "@/lib/theme-store";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({
  ssr: false,
  component: () => (
    <Protected>
      <SettingsPage />
    </Protected>
  ),
});

function SettingsPage() {
  const { user, updateProfile } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [saving, setSaving] = useState(false);
  const { theme, setTheme } = useTheme();

  useEffect(() => setName(user?.name ?? ""), [user?.name]);

  async function save() {
    if (!name.trim()) { toast.error("Name cannot be empty"); return; }
    if (name.trim() === user?.name) { toast.info("No changes to save"); return; }
    setSaving(true);
    try {
      await updateProfile({ name: name.trim() });
      toast.success("Profile updated");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  const themeOptions = [
    { value: "light" as const, label: "Light", icon: Sun },
    { value: "dark" as const, label: "Dark", icon: Moon },
  ];

  return (
    <AppShell title="Settings">
      <div className="mx-auto max-w-2xl space-y-6">

        {/* Profile */}
        <section className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-sm font-semibold">Profile</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Manage how you appear in OpsLens.
          </p>

          <div className="mt-5 space-y-4">
            {/* Avatar */}
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/20 text-xl font-bold text-primary">
                {user?.name?.[0]?.toUpperCase() ?? "?"}
              </div>
              <div>
                <p className="text-sm font-medium">{user?.name}</p>
                <p className="text-xs text-muted-foreground">{user?.email}</p>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input value={user?.email ?? ""} readOnly disabled />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Role</Label>
                <div>
                  <span className="inline-flex items-center rounded-md border border-border bg-card-elevated px-2 py-0.5 text-xs font-medium capitalize">
                    {user?.role ?? "member"}
                  </span>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Organisation ID</Label>
                <Input value={String(user?.organization_id ?? "")} readOnly disabled />
              </div>
            </div>
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </section>

        {/* Appearance */}
        <section className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-sm font-semibold">Appearance</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Choose your preferred colour scheme.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {themeOptions.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all",
                  theme === value
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card-elevated hover:border-primary/40",
                )}
              >
                <Icon className={cn("h-5 w-5", theme === value ? "text-primary" : "text-muted-foreground")} />
                <div>
                  <p className={cn("text-sm font-medium", theme === value && "text-primary")}>
                    {label}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {value === "light" ? "Clean & bright" : "Easy on the eyes"}
                  </p>
                </div>
                {theme === value && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-primary" />
                )}
              </button>
            ))}
          </div>
        </section>

      </div>
    </AppShell>
  );
}
