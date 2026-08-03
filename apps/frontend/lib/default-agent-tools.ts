/** OpenAI-style tool definitions for the Phase 6.5 worker registry (http_fetch, web_search, file_write). */
export const DEFAULT_AGENT_TOOLS_CONFIG = {
  tools: [
    {
      type: "function" as const,
      function: {
        name: "http_fetch",
        description: "Fetch a public HTTP(S) URL (GET only) with SSRF protection.",
        parameters: {
          type: "object",
          properties: {
            url: { type: "string", description: "HTTP or HTTPS URL to GET" },
          },
          required: ["url"],
        },
      },
    },
    {
      type: "function" as const,
      function: {
        name: "web_search",
        description: "Search the public web via Tavily (requires Tavily API key).",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string" },
          },
          required: ["query"],
        },
      },
    },
    {
      type: "function" as const,
      function: {
        name: "file_write",
        description: "Write a file under the run artifact directory.",
        parameters: {
          type: "object",
          properties: {
            filename: { type: "string" },
            content: { type: "string", description: "File body (utf-8 text)" },
          },
          required: ["filename", "content"],
        },
      },
    },
  ],
};
