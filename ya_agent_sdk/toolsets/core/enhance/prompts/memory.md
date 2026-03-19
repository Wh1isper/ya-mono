<memory-guidelines>

<overview>
Memory tool for persisting key-value information across conversation turns.
Stored entries are automatically injected into your context on every user message.
Use this to remember important facts, decisions, and preferences within the session.
</overview>

<when-to-use>
- User states a preference that should be remembered for this session
- Important facts or decisions that you need to recall later
- Context that would be lost after summarize/compact
- Intermediate results worth preserving
</when-to-use>

<best-practices>
- Use descriptive, stable keys (e.g., "user-language", "project-framework")
- Keep values concise -- memory is injected every turn
- Delete entries when they are no longer relevant
- Do not store large data -- use files instead
</best-practices>

</memory-guidelines>
