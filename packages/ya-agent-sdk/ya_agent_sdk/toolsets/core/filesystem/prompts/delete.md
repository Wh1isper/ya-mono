<delete-tool>
Delete files or directories within the working directory.

<parameters>
- `paths`: List of file or directory paths to delete.
- `recursive`: Delete directories and their contents, equivalent to `rm -r`.
- `force`: Ignore missing paths, equivalent to `rm -f`.
</parameters>

<best-practices>
- Use `paths` for multiple deletions in one call.
- Use `recursive=true` for non-empty directories when you intend `rm -r` behavior.
- Use `force=true` when cleanup should succeed even if paths are already gone, equivalent to `rm -f`.
- Use `recursive=true` and `force=true` together for `rm -rf` behavior.
- Prefer specific file or directory paths over broad parent directories.
- Verify broad recursive targets with `ls` or `glob` before deleting.
</best-practices>
</delete-tool>
