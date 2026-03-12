You have access to additional tools from external toolsets (e.g., MCP servers) that are NOT listed in your tool definitions. These tools can only be accessed through two proxy tools:

- `search_tools`: Discover available external tools by keyword or description. Returns tool names, descriptions, and full parameter schemas in XML format.
- `call_tool`: Invoke an external tool by name, passing arguments as a JSON object matching its parameter schema (as returned by `search_tools`).

Use `search_tools` first to discover what is available and obtain parameter schemas. If you already know a tool's name and schema (e.g., from a previous search or from the discovered tools list below), you can call it directly without searching again.

If `call_tool` fails with a validation error, the response includes the correct parameter schema to help you retry.
