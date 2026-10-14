# GitHub Bridge

The built-in `github` bridge connects an ordinary GitHub service account to YA Claw without a GitHub App, webhook, public callback, tunnel, or relay. YA Claw makes outbound REST requests to the account's notification inbox and maps each Issue or Pull Request to one durable session.

## GitHub Account and Token

Use a dedicated ordinary GitHub account and grant that account access only to the repositories it should operate on. Create a classic personal access token for that account.

GitHub's Notifications REST endpoints do not support fine-grained personal access tokens:

- use classic scope `notifications` for the notification inbox
- use classic scope `repo` when private repository subjects, comments, code, pushes, or Pull Requests must be read or modified

Organization SSO policy may require explicit authorization of the classic PAT. Repository membership, PAT scope, and GitHub notification subscriptions are the authority boundary; YA Claw does not maintain a second repository allowlist.

Never bake the PAT into a Docker image. Supply it as a runtime environment value.

## Service Configuration

```env
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=github
YA_CLAW_BRIDGE_GITHUB_TOKEN=replace-with-classic-pat
YA_CLAW_BRIDGE_GITHUB_ALLOWED_SENDERS=alice,bob
YA_CLAW_BRIDGE_GITHUB_DEFAULT_PROFILE=default
YA_CLAW_BRIDGE_GITHUB_API_URL=https://api.github.com
YA_CLAW_BRIDGE_GITHUB_POLL_INTERVAL_SECONDS=60
YA_CLAW_BRIDGE_GITHUB_MAX_SOURCE_NOTIFICATION_DELAY_SECONDS=600
YA_CLAW_BRIDGE_GITHUB_INITIAL_LOOKBACK_SECONDS=0
YA_CLAW_BRIDGE_GITHUB_MARK_READ=true
```

`YA_CLAW_BRIDGE_GITHUB_ALLOWED_SENDERS` accepts comma-separated, case-insensitive exact GitHub logins. Use `*` to accept any attributable author except the authenticated account. Every accepted source must explicitly mention that account in its own body; wildcard authorization never bypasses mention or attribution checks.

`YA_CLAW_BRIDGE_GITHUB_INITIAL_LOOKBACK_SECONDS=0` starts from bridge initialization time and avoids creating sessions from historical notifications. Set a positive value to process a bounded initial lookback.

`YA_CLAW_BRIDGE_GITHUB_MAX_SOURCE_NOTIFICATION_DELAY_SECONDS` controls sender attribution delay tolerance, not polling frequency or cursor overlap. It defaults to `600` seconds, accepts non-negative integers, and requires identical timestamps when set to `0`. A larger window also widens the heuristic association with an older source; it does not make subject edits attributable.

## Notification and Session Behavior

The adapter scans all notification reasons. It does not have an event-type allowlist. Only `Issue` and `PullRequest` subjects become YA Claw events; other notification subjects are optionally marked read and ignored.

GitHub notifications are mutable thread snapshots rather than individual events. YA Claw uses:

- tenant: API host plus authenticated account ID
- conversation: repository ID plus Issue/PR kind and number
- comment event/message ID: repository ID, comment kind/ID, and comment `updated_at`
- subject-only event/message ID: notification thread ID plus `updated_at`

Repeated explicit mentions on one Issue or Pull Request continue the same persisted session, including after run completion or service restart, while retaining distinct idempotency keys. A new comment or notification thread ID does not create a new session. Different resources remain isolated. The session omits a custom workspace binding and inherits `YA_CLAW_WORKSPACE_DIR` or the configured default mount set.

The adapter follows `latest_comment_url` when available. A distinct comment source must explicitly mention the authenticated account and pass the configured attribution delay window (10 minutes by default). GitHub may return the subject URL itself as `latest_comment_url`; normalized equivalent URLs are treated as the subject. A newly created Issue/PR body with a direct account mention may be accepted for `mention` or `team_mention` notification reasons when `created_at` equals `updated_at` and the notification falls within the configured delay window. Other subject-only reasons and later subject edits cannot reliably identify the actor and are rejected even with `*`. A team mention or `reason=mention` alone is insufficient.

The adapter also paginates the resource's conversation comments and, for PRs, review comments. It recovers actual comments when `latest_comment_url` points to the subject or a later activity. Every comment, including follow-ups, must explicitly mention the authenticated account; comments without a mention create no event, run, session, or reaction. Matching is case-insensitive with exact login boundaries, using body text rather than Markdown parsing. Explicit mentions can recover older requests independently of notification delay; all comments still require an allowed author and exclude the bot itself. Edited comments are new versions only while their current body contains the mention; removing it does not cancel previously accepted work. Multiple eligible comments are delivered in chronological order. Older explicit requests not already ingested may therefore be recovered when their resource next appears in the notification inbox; this is not a global historical-notification replay. Existing records for already-ingested comment versions retain their delivery identity across upgrade.

After durable ingestion, the bridge adds an `eyes` reaction to the actual comment. It sends no acknowledgement comment and does not instruct the model to send one. The event's `normalized_event.metadata.github.eyes_reaction` records `pending`, `sent`, or `unavailable`; pending reactions retry independently on later polls and after restart, even without another notification. A reaction failure never resubmits an accepted input. Pending pre-upgrade reactions whose stored source body has no direct mention are skipped; existing accepted runs and sent reactions are not removed. Check PAT permissions if acknowledgements remain pending; 404/410 targets are logged and marked unavailable. The existing event JSON stores this state without a database migration.

## Polling and Cursor

Polling uses:

```text
GET /notifications?all=true&since=<durable cursor>
```

The adapter follows `Link: rel="next"` pagination with `per_page=50`, sends `If-Modified-Since`, and waits for the greater of `YA_CLAW_BRIDGE_GITHUB_POLL_INTERVAL_SECONDS` and GitHub's `X-Poll-Interval` response header.

The durable cursor lives in `bridge_cursors`. Established cursors replay a 60-second overlap and rely on the versioned `bridge_events` uniqueness boundary for dedupe. After a complete scan, the cursor advances to the first GitHub response's `Date` timestamp, falling back to the local scan start only when that header is unavailable. This avoids advancing beyond GitHub when the host clock is fast.

When mark-read is enabled, successfully handled and ignored notification threads are marked read on a best-effort basis. Failed dispatches are retried without advancing the cursor or marking the thread read; existing `received` or `failed` event records reconcile an already-persisted run or deferred HITL input before resubmission. The adapter never marks threads done. Delivery correctness depends on `all=true`, the local cursor, and durable event IDs rather than GitHub unread state.

## Workspace GitHub CLI

`YA_CLAW_BRIDGE_GITHUB_TOKEN` is automatically injected into every workspace environment as `GH_TOKEN`. The official workspace image includes `gh`, so agents can inspect and act on the current resource:

```bash
gh auth status
gh issue view 123 --repo owner/repo --comments
gh pr view 456 --repo owner/repo --comments
gh issue comment 123 --repo owner/repo --body 'Reply text'
gh pr comment 456 --repo owner/repo --body 'Reply text'
```

The GitHub-specific bridge prompt tells the agent to inspect the current resource before acting because multiple GitHub updates may have been coalesced into one notification snapshot.

For Docker workspaces, environment values are fixed when the session container is created. Recreate active GitHub session containers after rotating the PAT:

```bash
docker rm -f ya-claw-session-<session-short>-g<generation>
rm -f /var/lib/ya-claw/data/docker-workspace-containers/sessions/<session-id>/workspace.json
```

## Network Boundary

YA Claw requires outbound HTTPS access to the configured GitHub API origin, and plaintext HTTP API URLs are rejected. No inbound GitHub connection is required. The REST client sends authorization only to the exact configured API origin and rejects foreign-origin subject/comment URLs.

## Verification

Check service logs for:

- authenticated account and derived tenant
- effective sender allowlist and poll interval
- ignored unsupported subjects
- ignored disallowed or unresolved senders
- dispatched event ID, repository, Issue/PR number, session ID, and run ID
- transient poll failures and mark-read failures
- pending acknowledgement retries and unavailable reaction targets

Check the workspace container:

```bash
docker exec -it ya-claw-session-<session-short>-g<generation> gh --version
docker exec -it ya-claw-session-<session-short>-g<generation> sh -lc 'test -n "$GH_TOKEN"'
docker exec -it ya-claw-session-<session-short>-g<generation> gh auth status
```

Inspect bridge records through the authenticated API:

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  'http://127.0.0.1:9042/api/v1/bridges/events?adapter=github'

curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  'http://127.0.0.1:9042/api/v1/bridges/conversations?adapter=github'
```

## Operational Limits

- One YA Claw process runs one GitHub adapter/account.
- Notifications can coalesce intermediate actions and are not a lossless audit stream.
- Non-Issue/PR notifications never create sessions.
- Deleted source resources are ignored and optionally marked read.
- Token or API bootstrap failures are retried on the polling interval.

## Official GitHub References

- Notifications API: <https://docs.github.com/en/rest/activity/notifications>
- List notifications: <https://docs.github.com/en/rest/activity/notifications#list-notifications-for-the-authenticated-user>
- Mark a thread read: <https://docs.github.com/en/rest/activity/notifications#mark-a-thread-as-read>
- Issue comments: <https://docs.github.com/en/rest/issues/comments#list-issue-comments>
- PR review comments: <https://docs.github.com/en/rest/pulls/comments#list-review-comments-on-a-pull-request>
- Comment reactions: <https://docs.github.com/en/rest/reactions/reactions#create-reaction-for-an-issue-comment>
