import { redirect } from "next/navigation";

import { type ReactElement } from "react";

export default function ConnectedToolsPage(): ReactElement {
  redirect("/dashboard/vault");
}
