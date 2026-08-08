import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyStateCommandCenter } from "@/components/command-center/empty-state";

const AGENTS_HREF = "/dashboard/projects/p1/agent-definitions";

describe("EmptyStateCommandCenter quickstart", () => {
  it("renders the real four-step dependency chain", () => {
    render(
      <EmptyStateCommandCenter
        state={{ hasProject: false, hasCredential: false, hasAgent: false, agentsHref: null }}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getAllByTestId("quickstart-title").map((h) => h.textContent)).toEqual([
      "PROJECT",
      "CREDENTIAL",
      "AGENT",
      "RUN",
    ]);
  });

  it("marks completed steps and points the CTA at the next one", () => {
    render(
      <EmptyStateCommandCenter
        state={{ hasProject: true, hasCredential: false, hasAgent: false, agentsHref: AGENTS_HREF }}
      />,
    );

    expect(screen.getByTestId("quickstart-step-01").getAttribute("data-state")).toBe("done");
    expect(screen.getByTestId("quickstart-step-02").getAttribute("data-state")).toBe("current");
    expect(screen.getByTestId("quickstart-step-03").getAttribute("data-state")).toBe("pending");

    const cta = screen.getByRole("link", { name: "+ ADD CREDENTIAL" });
    expect(cta.getAttribute("href")).toBe("/dashboard/vault");
  });

  it("advances to the agent step once a credential exists", () => {
    render(
      <EmptyStateCommandCenter
        state={{ hasProject: true, hasCredential: true, hasAgent: false, agentsHref: AGENTS_HREF }}
      />,
    );

    expect(screen.getByTestId("quickstart-step-02").getAttribute("data-state")).toBe("done");
    expect(screen.getByTestId("quickstart-step-03").getAttribute("data-state")).toBe("current");
    expect(screen.getByRole("link", { name: "+ NEW AGENT" }).getAttribute("href")).toBe(AGENTS_HREF);
  });
});
