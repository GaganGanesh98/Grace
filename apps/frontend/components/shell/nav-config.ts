import {
  BookOpenCheck,
  Bot,
  ClipboardCheck,
  FileCheck2,
  FolderKanban,
  KeyRound,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Only the exact path counts as active (the dashboard root). */
  exact?: boolean;
};

export type NavGroup = { label: string; items: NavItem[] };

// Phase 8.3 shell: Lovable's grouped navigation, pointed at the real /dashboard routes.
export const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [{ href: "/dashboard", label: "Command center", icon: LayoutDashboard, exact: true }],
  },
  {
    label: "Governance",
    items: [
      { href: "/dashboard/receipts", label: "Receipts", icon: FileCheck2 },
      { href: "/dashboard/approvals", label: "Approvals", icon: ClipboardCheck },
      { href: "/dashboard/ledger", label: "Governance ledger", icon: BookOpenCheck },
      { href: "/dashboard/policies", label: "Policies", icon: ShieldCheck },
    ],
  },
  {
    label: "Workspace",
    items: [
      { href: "/dashboard/projects", label: "Projects", icon: FolderKanban },
      { href: "/dashboard/agents", label: "Agents", icon: Bot },
      { href: "/dashboard/vault", label: "Vault", icon: KeyRound },
    ],
  },
  { label: "Account", items: [{ href: "/dashboard/settings", label: "Settings", icon: Settings }] },
];

export const navItems: NavItem[] = navGroups.flatMap((g) => g.items);

export function isNavActive(item: NavItem, pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (item.exact) {
    return path === item.href;
  }
  return path === item.href || path.startsWith(`${item.href}/`);
}

const SEGMENT_LABELS: Record<string, string> = {
  "agent-definitions": "Agents",
  "connected-tools": "Connected tools",
  agents: "Agents",
  approvals: "Approvals",
  ledger: "Governance ledger",
  members: "Members",
  policies: "Policies",
  projects: "Projects",
  receipts: "Receipts",
  runs: "Runs",
  settings: "Settings",
  vault: "Vault",
};

export type Crumb = { href: string; label: string; mono: boolean };

/**
 * Breadcrumb trail for a /dashboard path. Known segments get their nav label;
 * anything else is an id — shown as a project name when `nameFor` knows it,
 * otherwise shortened.
 */
export function breadcrumbFor(pathname: string, nameFor?: (segment: string) => string | undefined): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  if (segments[0] !== "dashboard" || segments.length === 1) {
    return [
      { href: "/dashboard", label: "Overview", mono: false },
      { href: "/dashboard", label: "Command center", mono: false },
    ];
  }
  const crumbs: Crumb[] = [];
  let href = "/dashboard";
  for (const segment of segments.slice(1)) {
    href = `${href}/${segment}`;
    const known = SEGMENT_LABELS[segment];
    if (known) {
      crumbs.push({ href, label: known, mono: false });
      continue;
    }
    const named = nameFor?.(segment);
    crumbs.push(
      named
        ? { href, label: named, mono: false }
        : { href, label: segment.length > 12 ? `${segment.slice(0, 8)}…` : segment, mono: true },
    );
  }
  return crumbs;
}
