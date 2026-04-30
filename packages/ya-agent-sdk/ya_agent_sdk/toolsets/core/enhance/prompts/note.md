<note-guidelines>

<overview>
Note tools persist key-value information across conversation turns.
Runtime context includes note keys so you know what is available, and note values are read on demand with `note_get`.
</overview>

<tools>
- `note`: Create, update, or delete a note entry.
- `note_get`: Read a note entry by key, or omit key to read all note entries.
</tools>

<when-to-use>
- User states a preference that should be remembered for this session
- Important facts or decisions that you need to recall later
- Context that would be lost after summarize/compact
- Intermediate results worth preserving
</when-to-use>

<best-practices>
- Use descriptive, stable keys (e.g., "user-language", "project-framework")
- Keep values concise and delete entries when they are stale
- Use `note_get` when runtime context lists a relevant note key and the value is needed for the current task
- Store large data in files and keep only the file path or index in notes
</best-practices>

</note-guidelines>
