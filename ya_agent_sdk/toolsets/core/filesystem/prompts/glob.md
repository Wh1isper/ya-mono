<glob-tool>
Fast file pattern matching for any codebase size.
Returns paths sorted by modification time (newest first).
Results are limited to 500 by default to avoid oversized output.

<patterns>
- `**/*.py` - All Python files recursively
- `src/**/*.ts` - TypeScript files under src/
- `*.json` - JSON files in current directory
</patterns>

<best-practices>
- Use specific patterns to narrow results
- Prefer glob over ls for finding files by extension
- Combine with grep for content + pattern filtering
- Files in .gitignore are excluded by default; set include_ignored=true to search ignored files (e.g., node_modules/, .venv/, build/)
- Default max_results is 500; increase or set to -1 (unlimited) only when needed
- Very large results are saved to a temp file with `output_file_path`; use view tool to read it
</best-practices>
</glob-tool>
