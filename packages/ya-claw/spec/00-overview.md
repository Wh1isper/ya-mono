# 00 - Overview

## Definition

YA Claw is a workspace-native single-node runtime web service for `ya-agent-sdk`.

It provides a durable local execution shell around SDK agent construction and streaming primitives with:

- reusable agent profiles
- provider-resolved workspaces
- resumable sessions and runs
- session schedules for timed execution
- in-process async task coordination
- live event streaming for the current node
- bridge adapters for external IM channels
- artifact persistence
- a first-party web shell

## Goals

### Product Goals

- make local and self-hosted deployment the default operating model
- treat workspace resolution as a first-class runtime concern
- preserve SDK capabilities such as continuation, subagents, compact, and streaming
- keep the runtime small enough to understand and evolve quickly
- keep active state management inside one process for the single-node target
- support both scheduled session execution and channel-driven execution through one service

### Non-Goals

- hosted platform concerns
- organization-level control plane design
- distributed runtime scheduling
- bridge provider feature parity freeze before first implementation

## Top-level Architecture

```mermaid
flowchart TB
    subgraph Clients
        WEB[YA Claw Web]
        API_CLIENT[API Clients]
        CLI[ya-claw CLI]
        IM[IM Platforms]
    end

    subgraph Runtime[YA Claw Service]
        API[HTTP API]
        CFG[Config Resolver]
        WSP[Workspace Resolver]
        EXEC[Execution Coordinator]
        SESS[Session Manager]
        TASKS[Async Task Registry]
        SCHED[Schedule Dispatcher]
        BRIDGE[Bridge Relay Manager]
        EVT[Event Fan-out]
    end

    subgraph SDK[ya-agent-sdk]
        AGENT[create_agent]
        STREAM[stream_agent]
        CTX[AgentContext]
        ENV[Environment]
    end

    subgraph Storage[Runtime Storage]
        SQL[(SQLite / PostgreSQL)]
        MEM[(In-Process Memory)]
        FS[(Local Filesystem)]
    end

    WEB --> API
    API_CLIENT --> API
    CLI --> API
    IM --> BRIDGE
    BRIDGE --> API

    API --> CFG
    API --> WSP
    API --> EXEC
    API --> SESS
    API --> TASKS
    API --> SCHED
    API --> BRIDGE

    EXEC --> AGENT
    EXEC --> STREAM
    EXEC --> CTX
    EXEC --> ENV

    EXEC --> SQL
    EXEC --> MEM
    EXEC --> FS
    SESS --> SQL
    TASKS --> MEM
    SCHED --> MEM
    BRIDGE --> MEM
    EVT --> MEM
    WSP --> FS
```

## Runtime Boundary

| Concern                    | Owner                     |
| -------------------------- | ------------------------- |
| Agent execution primitives | `ya-agent-sdk`            |
| Workspace resolution       | YA Claw                   |
| Session persistence        | YA Claw                   |
| Run orchestration          | YA Claw                   |
| Schedule dispatch          | YA Claw                   |
| Bridge relay coordination  | YA Claw                   |
| Active task tracking       | YA Claw                   |
| Event delivery             | YA Claw                   |
| Artifact persistence       | YA Claw                   |
| Channel transport          | bridge adapter            |
| LLM provider interaction   | SDK + model provider      |
| Container lifecycle        | user or external operator |

## Core Runtime Objects

The architecture revolves around a small set of runtime objects:

- **Workspace**: a named execution target known to the runtime
- **Workspace Binding**: the resolved execution snapshot returned by `WorkspaceProvider`
- **Agent Profile**: reusable runtime configuration for model, prompt, tools, and policy
- **Session**: durable conversational continuity
- **Run**: one execution attempt inside a session
- **Session Schedule**: a timed trigger bound to one session template or continuation target
- **Async Task**: an in-process background activity associated with one runtime process
- **Bridge Endpoint**: one configured channel integration and relay policy
- **Artifact**: durable file output or retained input produced by a run

These objects are architectural concepts first. Exact table layouts should stay implementation-driven.

## Bridge Model

A bridge links an IM platform to the YA Claw service through a dedicated adapter.

The base interaction path is:

```text
IM <-> Bridge <-> YA Claw Service
```

Bridge adapters should support two relay modes:

- **Task Relay**: the bridge submits work to an async session flow and delivers agent output through the channel adapter or channel CLI
- **Stream Relay**: the bridge starts a foreground run, consumes SSE from YA Claw, and forwards channel-ready output in near real time

## Deployment Baseline

The reference deployment shape is:

- one YA Claw web service
- one in-process runtime state manager
- one session scheduler
- one bridge subsystem
- one SQLite database by default
- optional PostgreSQL when an external relational store is preferred
- one local data directory
- one bundled SPA web shell

That shape is the baseline for the rest of this spec.
