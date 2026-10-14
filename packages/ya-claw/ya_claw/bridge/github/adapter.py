from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.bridge.base import BridgeAdapter, BridgeMessageHandler
from ya_claw.bridge.github.client import GitHubApiError, GitHubClient, GitHubRestClient
from ya_claw.bridge.github.models import (
    GitHubNotification,
    GitHubNotificationResource,
    GitHubNotificationSource,
    GitHubUser,
)
from ya_claw.bridge.github.normalizer import (
    build_inbound_message,
    comment_mentions_user,
    resolve_comment_source,
    resolve_notification_resource,
    resolve_notification_source,
    source_sender_is_attributable,
)
from ya_claw.bridge.models import BridgeAdapterType, BridgeEventStatus, BridgeInboundMessage
from ya_claw.config import ClawSettings
from ya_claw.orm.tables import BridgeCursorRecord, BridgeEventRecord

_CURSOR_KEY = "notifications"
_CURSOR_OVERLAP = timedelta(seconds=60)
_ACCEPTED_STATUSES = frozenset({
    BridgeEventStatus.QUEUED,
    BridgeEventStatus.SUBMITTED,
    BridgeEventStatus.STEERED,
    BridgeEventStatus.DEFERRED,
    BridgeEventStatus.DUPLICATE,
})


class GitHubBridgeAdapter(BridgeAdapter):
    def __init__(
        self,
        *,
        settings: ClawSettings,
        handler: BridgeMessageHandler,
        session_factory: async_sessionmaker[AsyncSession],
        client: GitHubClient | None = None,
    ) -> None:
        self._settings = settings
        self._handler = handler
        self._session_factory = session_factory
        self._client = client
        self._owns_client = client is None
        self._stop_event = asyncio.Event()
        self._tenant_key: str | None = None
        self._bot_user: GitHubUser | None = None
        self._cursor_at: datetime | None = None
        self._cursor_has_history = False

    @property
    def adapter_type(self) -> BridgeAdapterType:
        return BridgeAdapterType.GITHUB

    async def run(self) -> None:
        token = self._settings.bridge_github_token_value
        if token is None:
            raise RuntimeError("GitHub bridge requires YA_CLAW_BRIDGE_GITHUB_TOKEN.")
        allowed_senders = self._settings.resolved_bridge_github_allowed_senders
        if not allowed_senders:
            raise RuntimeError(
                "GitHub bridge requires YA_CLAW_BRIDGE_GITHUB_ALLOWED_SENDERS with one or more GitHub logins or '*'."
            )
        if self._client is None:
            self._client = GitHubRestClient(
                token=token,
                api_url=self._settings.bridge_github_api_url,
                user_agent=f"ya-claw/{self._settings.resolved_service_version}",
            )

        client = self._require_client()
        self._stop_event.clear()
        try:
            while not self._stop_event.is_set():
                delay_seconds = int(self._settings.bridge_github_poll_interval_seconds)
                try:
                    if self._tenant_key is None:
                        await self._bootstrap(allowed_senders)
                    await self._retry_pending_reactions()
                    response_interval = await self._poll_once()
                    if response_interval is not None:
                        delay_seconds = max(delay_seconds, response_interval)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("GitHub bridge notification poll failed")
                await self._wait_for_next_poll(delay_seconds)
        finally:
            if self._owns_client:
                await client.close()
            self._client = None
            self._bot_user = None
            self._tenant_key = None
            self._cursor_at = None
            self._cursor_has_history = False
            logger.info("GitHub bridge adapter stopped")

    async def stop(self) -> None:
        self._stop_event.set()

    async def _bootstrap(self, allowed_senders: set[str]) -> None:
        bot_user = await self._require_client().get_authenticated_user()
        self._bot_user = bot_user
        self._tenant_key = _tenant_key(self._settings.bridge_github_api_url, bot_user)
        self._cursor_at, created = await self._load_or_create_cursor(self._tenant_key)
        self._cursor_has_history = not created
        logger.info(
            "Starting GitHub bridge adapter account={} tenant={} allowed_senders={} poll_interval_seconds={} max_source_notification_delay_seconds={}",
            bot_user.login,
            self._tenant_key,
            sorted(allowed_senders),
            self._settings.bridge_github_poll_interval_seconds,
            self._settings.bridge_github_max_source_notification_delay_seconds,
        )

    async def _poll_once(self) -> int | None:
        client = self._require_client()
        tenant_key = self._require_tenant_key()
        cursor_at = self._require_cursor()
        scan_started_at = datetime.now(UTC)
        since = cursor_at - _CURSOR_OVERLAP if self._cursor_has_history else cursor_at
        page = await client.list_notifications(since=since)

        for notification in sorted(page.notifications, key=lambda item: (item.updated_at, item.id)):
            await self._process_notification(notification, tenant_key=tenant_key)

        cursor_at = page.response_date or scan_started_at
        await self._save_cursor(tenant_key, cursor_at)
        self._cursor_at = cursor_at
        self._cursor_has_history = True
        return page.poll_interval_seconds

    async def _process_notification(self, notification: GitHubNotification, *, tenant_key: str) -> None:
        resource = resolve_notification_resource(notification)
        if resource is None:
            logger.debug(
                "Ignoring GitHub notification without an Issue/PR resource thread_id={} subject_type={}",
                notification.id,
                notification.subject.type,
            )
            await self._mark_read(notification.id)
            return

        try:
            sources = await self._load_sources(notification, resource)
        except GitHubApiError as exc:
            if exc.status_code not in {404, 410}:
                raise
            logger.info(
                "Ignoring GitHub notification whose source no longer exists thread_id={} repository={} status_code={}",
                notification.id,
                notification.repository.full_name,
                exc.status_code,
            )
            await self._mark_read(notification.id)
            return
        for source in sources:
            if not self._sender_allowed(source.sender):
                logger.info(
                    "Ignoring GitHub notification from disallowed or unresolved sender thread_id={} repository={} resource={}#{} sender={}",
                    notification.id,
                    notification.repository.full_name,
                    resource.kind,
                    resource.number,
                    source.sender.login if source.sender is not None else None,
                )
                continue
            await self._dispatch_source(notification, resource, source, tenant_key=tenant_key)
        await self._mark_read(notification.id)

    async def _dispatch_source(
        self,
        notification: GitHubNotification,
        resource: GitHubNotificationResource,
        source: GitHubNotificationSource,
        *,
        tenant_key: str,
    ) -> None:
        message = build_inbound_message(
            notification,
            tenant_key=tenant_key,
            resource=resource,
            source=source,
        )
        if source.comment_url is not None:
            message = await self._reuse_legacy_comment_identity(message, source)
        result = await self._handler.handle_message(message)
        if result.status not in _ACCEPTED_STATUSES:
            raise RuntimeError(
                f"GitHub bridge dispatch failed for event '{message.event_id}': "
                f"{result.error_message or 'unknown bridge dispatch error'}"
            )
        logger.info(
            "GitHub bridge dispatched event_id={} repository={} resource={}#{} sender={} status={} session_id={} run_id={}",
            message.event_id,
            notification.repository.full_name,
            resource.kind,
            resource.number,
            source.sender.login if source.sender is not None else None,
            result.status,
            result.session_id,
            result.run_id,
        )
        if source.comment_url is not None:
            await self._acknowledge_comment(message)

    async def _load_sources(
        self, notification: GitHubNotification, resource: GitHubNotificationResource
    ) -> list[GitHubNotificationSource]:
        bot_user = self._bot_user
        if bot_user is None:
            raise RuntimeError("GitHub bridge account has not been resolved.")
        payload, attributable = await self._load_source(notification)
        latest_url = notification.subject.latest_comment_url
        direct_comment = (
            latest_url is not None
            and not _same_source_url(latest_url, notification.subject.url)
            and isinstance(payload, dict)
        )
        sources: dict[str, GitHubNotificationSource] = {}
        if (
            direct_comment
            and attributable
            and isinstance(payload, dict)
            and comment_mentions_user(payload, bot_user.login)
        ):
            source = resolve_comment_source(
                notification,
                payload,
                api_url=self._settings.bridge_github_api_url,
                review_comment="/pulls/comments/" in (latest_url or ""),
            )
            if source is not None and source.comment_event_id is not None:
                sources[source.comment_event_id] = source

        # Notifications are wake-ups, not actor-bearing events. Recover explicit
        # requests from real comments even when the snapshot points at the subject
        # or a later comment. Never assign the subject author's identity to them.
        comments = await self._require_client().list_comments(
            repository=notification.repository.full_name,
            number=resource.number,
            pull_request=resource.kind == "pull",
        )
        for comment in comments:
            if not comment_mentions_user(comment, bot_user.login):
                continue
            source = resolve_comment_source(
                notification,
                comment,
                api_url=self._settings.bridge_github_api_url,
                review_comment="pull_request_review_id" in comment,
            )
            if source is not None and source.comment_event_id is not None:
                sources[source.comment_event_id] = source
        allowed_comments = [source for source in sources.values() if self._sender_allowed(source.sender)]
        if allowed_comments:
            return sorted(
                allowed_comments,
                key=lambda source: (str((source.payload or {}).get("updated_at")), source.comment_event_id or ""),
            )
        # Only a newly created, attributable subject with a direct mention may
        # trigger without a comment. Never turn a rejected comment into a subject
        # event, even with a wildcard sender allowlist.
        if (
            direct_comment
            or not attributable
            or not isinstance(payload, dict)
            or not comment_mentions_user(payload, bot_user.login)
        ):
            return []
        return [resolve_notification_source(payload, sender_is_attributable=True)]

    async def _load_source(self, notification: GitHubNotification) -> tuple[dict[str, object] | None, bool]:
        max_notification_delay = timedelta(seconds=self._settings.bridge_github_max_source_notification_delay_seconds)
        latest_comment_url = notification.subject.latest_comment_url
        if latest_comment_url is not None:
            try:
                payload = await self._require_client().get_json(latest_comment_url)
                return payload, source_sender_is_attributable(
                    notification,
                    payload,
                    source_is_comment=not _same_source_url(latest_comment_url, notification.subject.url),
                    max_notification_delay=max_notification_delay,
                )
            except GitHubApiError as exc:
                if exc.status_code not in {404, 410}:
                    raise
        subject_url = notification.subject.url
        if subject_url is None:
            return None, False
        payload = await self._require_client().get_json(subject_url)
        return payload, source_sender_is_attributable(
            notification,
            payload,
            source_is_comment=False,
            max_notification_delay=max_notification_delay,
        ) and latest_comment_url is None

    async def _reuse_legacy_comment_identity(
        self, message: BridgeInboundMessage, source: GitHubNotificationSource
    ) -> BridgeInboundMessage:
        """Retain delivery keys for comments already stored under notification IDs."""
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeEventRecord).where(
                    BridgeEventRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeEventRecord.tenant_key == message.tenant_key,
                    BridgeEventRecord.external_chat_id == message.chat_id,
                    BridgeEventRecord.event_id.startswith(f"github:{message.thread_id}:"),
                )
            )
            for record in result.scalars():
                github = record.normalized_event.get("metadata", {}).get("github", {})
                if github.get("comment_event_id") == source.comment_event_id:
                    return message.model_copy(
                        update={
                            "event_id": record.event_id,
                            "message_id": record.external_message_id or record.event_id,
                        }
                    )
                raw = record.raw_event
                payload = raw.get("resolved_source")
                subject = raw.get("subject")
                if not isinstance(payload, dict) or not isinstance(subject, dict) or source.payload is None:
                    continue
                url = subject.get("latest_comment_url")
                if (
                    isinstance(url, str)
                    and source.comment_url is not None
                    and _same_source_url(url, source.comment_url)
                    and payload.get("id") == source.payload.get("id")
                    and payload.get("updated_at") == source.payload.get("updated_at")
                ):
                    return message.model_copy(
                        update={
                            "event_id": record.event_id,
                            "message_id": record.external_message_id or record.event_id,
                        }
                    )
        return message

    async def _retry_pending_reactions(self) -> None:
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeEventRecord.normalized_event).where(
                    BridgeEventRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeEventRecord.tenant_key == self._require_tenant_key(),
                    BridgeEventRecord.status.in_(_ACCEPTED_STATUSES),
                    BridgeEventRecord.normalized_event["metadata"]["github"]["eyes_reaction"].as_string() == "pending",
                )
            )
            messages = [BridgeInboundMessage.model_validate(payload) for payload in result.scalars()]
        bot_user = self._bot_user
        if bot_user is None:
            raise RuntimeError("GitHub bridge account has not been resolved.")
        for message in messages:
            sender = GitHubUser(login=message.sender_id, id=-1) if message.sender_id is not None else None
            source = message.raw_event.get("resolved_source")
            if (
                self._sender_allowed(sender)
                and isinstance(source, dict)
                and comment_mentions_user(source, bot_user.login)
            ):
                await self._acknowledge_comment(message)

    async def _acknowledge_comment(self, message: BridgeInboundMessage) -> None:
        github = message.metadata.get("github")
        if not isinstance(github, dict) or not isinstance(github.get("comment_url"), str):
            return
        comment_url = github["comment_url"]
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeEventRecord).where(
                    BridgeEventRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeEventRecord.tenant_key == message.tenant_key,
                    BridgeEventRecord.event_id == message.event_id,
                )
            )
            record = result.scalar_one_or_none()
            if isinstance(record, BridgeEventRecord):
                metadata = record.normalized_event.get("metadata", {})
                stored_github = metadata.get("github", {})
                if stored_github.get("eyes_reaction") in {"sent", "unavailable"}:
                    return
                # Also enroll successfully ingested pre-comment-identity events.
                record.normalized_event = {
                    **record.normalized_event,
                    "metadata": {
                        **metadata,
                        "github": {
                            **stored_github,
                            "comment_url": comment_url,
                            "eyes_reaction": "pending",
                        },
                    },
                }
                await db_session.commit()
        try:
            await self._require_client().add_eyes_reaction(comment_url)
            state = "sent"
        except GitHubApiError as exc:
            if exc.status_code in {404, 410}:
                state = "unavailable"
                logger.warning(
                    "GitHub acknowledgement target disappeared event_id={} url={}", message.event_id, comment_url
                )
            else:
                logger.warning("GitHub acknowledgement pending retry event_id={} error={}", message.event_id, exc)
                return
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeEventRecord).where(
                    BridgeEventRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeEventRecord.tenant_key == message.tenant_key,
                    BridgeEventRecord.event_id == message.event_id,
                )
            )
            record = result.scalar_one_or_none()
            if isinstance(record, BridgeEventRecord):
                normalized = record.normalized_event
                metadata = normalized.get("metadata", {})
                record.normalized_event = {
                    **normalized,
                    "metadata": {**metadata, "github": {**metadata.get("github", {}), "eyes_reaction": state}},
                }
                await db_session.commit()

    def _sender_allowed(self, sender: GitHubUser | None) -> bool:
        if sender is None:
            return False
        bot_user = self._bot_user
        if bot_user is not None and (sender.id == bot_user.id or sender.login.casefold() == bot_user.login.casefold()):
            return False
        allowed_senders = self._settings.resolved_bridge_github_allowed_senders
        if "*" in allowed_senders:
            return True
        return sender.login.casefold() in allowed_senders

    async def _mark_read(self, thread_id: str) -> None:
        if not self._settings.bridge_github_mark_read:
            return
        try:
            await self._require_client().mark_thread_read(thread_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to mark GitHub notification thread as read thread_id={}", thread_id)

    async def _load_or_create_cursor(self, tenant_key: str) -> tuple[datetime, bool]:
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeCursorRecord).where(
                    BridgeCursorRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeCursorRecord.tenant_key == tenant_key,
                    BridgeCursorRecord.cursor_key == _CURSOR_KEY,
                )
            )
            record = result.scalar_one_or_none()
            if isinstance(record, BridgeCursorRecord):
                return _parse_cursor(record.cursor_value), False

            cursor_at = datetime.now(UTC) - timedelta(
                seconds=int(self._settings.bridge_github_initial_lookback_seconds)
            )
            db_session.add(
                BridgeCursorRecord(
                    id=uuid4().hex,
                    adapter=BridgeAdapterType.GITHUB,
                    tenant_key=tenant_key,
                    cursor_key=_CURSOR_KEY,
                    cursor_value=_serialize_cursor(cursor_at),
                )
            )
            await db_session.commit()
            return cursor_at, True

    async def _save_cursor(self, tenant_key: str, cursor_at: datetime) -> None:
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(BridgeCursorRecord).where(
                    BridgeCursorRecord.adapter == BridgeAdapterType.GITHUB,
                    BridgeCursorRecord.tenant_key == tenant_key,
                    BridgeCursorRecord.cursor_key == _CURSOR_KEY,
                )
            )
            record = result.scalar_one_or_none()
            if not isinstance(record, BridgeCursorRecord):
                raise TypeError(f"GitHub bridge cursor was not found for tenant '{tenant_key}'.")
            record.cursor_value = _serialize_cursor(cursor_at)
            await db_session.commit()

    async def _wait_for_next_poll(self, delay_seconds: int) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=max(delay_seconds, 1))
        except TimeoutError:
            return

    def _require_client(self) -> GitHubClient:
        if self._client is None:
            raise RuntimeError("GitHub bridge client is not initialized.")
        return self._client

    def _require_tenant_key(self) -> str:
        if self._tenant_key is None:
            raise RuntimeError("GitHub bridge tenant is not initialized.")
        return self._tenant_key

    def _require_cursor(self) -> datetime:
        if self._cursor_at is None:
            raise RuntimeError("GitHub bridge cursor is not initialized.")
        return self._cursor_at


def _tenant_key(api_url: str, user: GitHubUser) -> str:
    parsed = urlparse(api_url)
    host = parsed.netloc.casefold()
    return f"github:{host}:{user.id}"


def _same_source_url(left: str, right: str | None) -> bool:
    if right is None:
        return False
    try:
        left_url = urlparse(left)
        right_url = urlparse(right)
        left_port = left_url.port or (443 if left_url.scheme.casefold() == "https" else None)
        right_port = right_url.port or (443 if right_url.scheme.casefold() == "https" else None)
    except ValueError:
        return False
    return (
        left_url.scheme.casefold(),
        left_url.hostname.casefold() if left_url.hostname is not None else None,
        left_port,
        left_url.path.rstrip("/"),
        left_url.query,
    ) == (
        right_url.scheme.casefold(),
        right_url.hostname.casefold() if right_url.hostname is not None else None,
        right_port,
        right_url.path.rstrip("/"),
        right_url.query,
    )


def _serialize_cursor(value: datetime) -> str:
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_cursor(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
