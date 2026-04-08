<shell-tool>
Execute shell commands via `shell_exec`. Commands are executed via `/bin/sh -c` (or `/bin/bash -c` depending on environment).

Parameters:
- command (required): The shell command string to execute
- timeout_seconds (default 180): Maximum execution time in seconds
- environment: Environment variables as key-value pairs
- cwd: Working directory (relative or absolute path)
- background (default false): Run command in background, returns process_id immediately

Examples: `ls -la`, `npm install && npm run build`

Large outputs (>20KB) are saved to temporary files with paths in stdout_file_path/stderr_file_path.

<background-mode>
Set background=true for long-running commands (builds, servers, test suites).
Returns a process_id immediately. Manage with:
- shell_wait: Wait for or poll a background process
  - timeout_seconds=0: Poll -- drain current output immediately without waiting
  - timeout_seconds>0: Wait up to N seconds, then drain whatever is available
  - Returns is_running=true if process is still running
  - Output is incremental: each call returns new output since last drain
- shell_input: Write to a background process's stdin
  - Use for answering interactive prompts (y/n), sending REPL commands, or piping data
  - A trailing newline is added automatically (simulates pressing Enter)
  - Set close_stdin=true to send EOF after writing
- shell_kill: Terminate a running process (returns final buffered output)
- shell_status: List all background processes and their status

Completed background processes are automatically reported in context.
Use shell_wait only when you need results before proceeding.
</background-mode>

Avoid:
- find/grep for searching - use grep, glob instead
- cat/head/tail/ls to read files - use view and ls tools
- cd command - use cwd parameter instead
</shell-tool>
