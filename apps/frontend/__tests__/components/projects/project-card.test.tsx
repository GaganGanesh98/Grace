import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectCardAgentsSection } from "@/components/projects/project-card-agents";

describe("ProjectCardAgentsSection", () => {
  it("shows AGENTS (N) from definition count", () => {
    render(
      <ProjectCardAgentsSection
        projectId="p1"
        definitionCount={3}
        isActive
        receiptAgents={[]}
      />,
    );
    expect(screen.getByText(/AGENTS \(3\)/)).toBeTruthy();
  });

  it("shows empty copy when there are zero definitions", () => {
    render(
      <ProjectCardAgentsSection projectId="p1" definitionCount={0} isActive receiptAgents={[]} />,
    );
    expect(screen.getByText(/No agents yet/i)).toBeTruthy();
  });
});
