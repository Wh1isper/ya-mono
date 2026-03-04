<summarize-guidelines>

<overview>
The summarize tool captures current progress and starts fresh with a clean context.
Use it for two purposes: managing context size, and switching focus between topics or tasks.
</overview>

<communication>
When summarizing, communicate naturally with the user:
- "The conversation is getting long. Let me summarize our progress and continue."
- "Before we switch to the new task, let me summarize what we've done so far."
- "Let me organize our progress, then we can move on to [next topic]."

Do NOT use technical jargon like "context reset", "context window", or "token limit" with the user.
</communication>

<when-to-summarize>
**Context management** -- keep conversations productive:
- System reminder indicates approaching context limit
- Conversation has accumulated a lot of back-and-forth that is no longer relevant
- About to begin multi-step work that benefits from clean context

**Focus switching** -- transition cleanly between topics:
- User asks to work on a different topic or task
- Major task phase completed, moving to the next phase
- User explicitly asks to summarize and continue
</when-to-summarize>

<when-not-to-summarize>
- Summary already occurred in current conversation (context restored tag exists)
- Current task is a direct continuation with all context still relevant
- Simple follow-up questions or minor adjustments
</when-not-to-summarize>

<before-summarizing>
1. **Capture remaining work as tasks** if applicable:
   - Review existing tasks with `task_list`
   - Create new tasks for pending items with `task_create`

2. **Identify key files** being actively edited or referenced

3. **Note important decisions** -- architecture choices, user preferences

Task states are automatically preserved. Creating tasks ensures structured
continuity in the new context.
</before-summarizing>

<content-structure>
The `content` field should be concise but complete:

```
## User Intent
[What the user is trying to accomplish]

## Current State
[What has been done, current progress]

## Key Decisions
- [Decision 1]: [Rationale]
- [Decision 2]: [Rationale]

## Next Step
[Immediate action to take after summary]
```

Only include task context in content if additional explanation is needed beyond
what the task descriptions already capture.
</content-structure>

<auto-load-files>
Use `auto_load_files` for files needed immediately after summary:
- Source files being actively edited
- Key configuration files
- Important reference documents

Avoid large files, files already described in content, or temporary files.
</auto-load-files>

</summarize-guidelines>
