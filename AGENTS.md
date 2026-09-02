# Repository Guidance

- Keep this plugin thin. Hardware access belongs in `baud`, `blea`, or
  `embedded-debugger`, not in orchestration scripts.
- New host diagnostics must be read-only and must not enumerate, open, reset,
  flash, halt, resume, write to, or otherwise touch physical devices.
- Cross-tool workflows must preserve each component's identity checks,
  confirmation gates, bounded operations, structured evidence, and cleanup.
- Do not register component MCP servers in this orchestration plugin. Component
  plugins own those server lifecycles; duplicate registration creates ambiguous
  tools and redundant processes.
- Validate the plugin, every Skill, tests, and `git diff --check` before commit.
