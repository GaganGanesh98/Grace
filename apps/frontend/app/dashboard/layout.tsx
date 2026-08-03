import type { ReactElement, ReactNode } from "react";

import { DashboardLayoutClient } from "@/components/dashboard-layout-client";

export default function DashboardLayout({ children }: { children: ReactNode }): ReactElement {
  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
