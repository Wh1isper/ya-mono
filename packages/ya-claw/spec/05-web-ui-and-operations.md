# 05 - Web UI and Operations

YA Claw ships with a bundled web shell and a simple single-node operations model.

## Web Shell Goal

The web shell is the first-party runtime console.

It should let a user:

- choose or restore a `project_id`
- create and continue sessions
- manage schedules
- watch live run output
- read compacted conversation history for completed rounds
- inspect bridge endpoints and relay activity
- inspect run summaries

The web shell acts as an application on top of YA Claw.
It can remember the last used `project_id` in application state and send it back on the next run.
YA Claw does not need a runtime-managed project catalog for that flow.

## Web Shell Sections

```mermaid
flowchart LR
    HOME[Overview] --> SS[Sessions]
    HOME --> SC[Schedules]
    HOME --> BR[Bridges]
    SS --> RV[Run View]
    RV --> RS[Run Summary]
```

### Overview

Shows runtime health, active sessions, active schedules, bridge activity, and recent runs.

### Sessions

Shows session lineage, latest state, continuation entry points, and compacted conversation history loaded from `message.json` in the session store.

### Schedules

Shows next fire time, last run status, target session, delivery policy, and effective project selection.

### Bridges

Shows bridge endpoints, relay mode, recent dispatches, and channel health.

### Run View

Shows live event output, final summary, AGUI-aligned event flow, effective `project_id`, and error state when needed.

### Run Summary

Shows the final run result, commit metadata, and continuation readiness.

## Startup Flow

The default startup path is:

1. load environment configuration
2. initialize the relational store and in-process runtime state manager
3. initialize schedule dispatcher and bridge subsystem
4. run migrations when auto-migrate is enabled
5. mount API routes
6. mount bundled web assets when present

## Health Model

`/healthz` should report:

- service status
- relational storage connectivity
- in-process runtime state manager health
- schedule dispatcher health
- bridge subsystem health
- optional web bundle availability

## Logging

The runtime should emit structured logs for:

- startup configuration summary
- project resolution failures
- run lifecycle transitions
- schedule trigger and dispatch lifecycle
- bridge ingress and relay lifecycle
- event delivery failures
- shutdown and cleanup

## Local Deployment Baseline

Recommended local deployment shapes:

- one supervised process
- one Docker deployment
- one systemd-managed service on a host

Each shape should keep the same core baseline:

- one YA Claw web service
- one SQLite database by default
- optional PostgreSQL for external relational storage
- one persistent local data directory
- one configured workspace root
- in-process active state, schedule dispatch, and bridge coordination

## Bridge Operations

The bridge subsystem should live inside the `ya-claw` package as both:

- a `ya_claw.bridge` subpackage for adapter implementations
- a `ya-claw bridge` CLI group for operational commands

A bridge adapter may target platforms such as:

- Lark
- Slack
- Discord
- Telegram

## Docker Alignment

Three image definitions exist in the repository:

- `Dockerfile.ya-claw` for the active runtime
- `Dockerfile.ya-claw-workspace` for the default Docker workspace provider image
- `Dockerfile.ya-agent-platform` for the WIP stateless agent service image

### Docker Startup

The `ya-claw` image uses `tini` as PID 1 and runs `ya-claw start` as the default command.
The `start` command handles:

1. database migration when `YA_CLAW_AUTO_MIGRATE` is enabled
2. profile seeding when `YA_CLAW_AUTO_SEED_PROFILES` is enabled
3. HTTP server startup

This replaces the previous `start.sh` shell wrapper and keeps startup logic inside the Python CLI for consistent error handling and signal propagation.

## AGUI Web UI Model

The Web UI should follow an AGUI-aligned split:

- live session interaction comes from streamed events in process memory
- committed conversation history comes from `message.json` in the session store
- state restore views read `state.json` from the session store

## Operational Principle

Single-node operations should stay clear enough that one developer can inspect runtime health, storage, active runs, schedules, bridge activity, and committed conversation history through one service.
