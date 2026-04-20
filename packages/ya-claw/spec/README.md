# YA Claw Architecture Spec

YA Claw is a workspace-native single-node runtime web service built on top of `ya-agent-sdk`.

This spec set focuses on one clear target shape:

- one runtime service
- one in-process runtime state manager
- one session scheduler
- one bridge subsystem
- one SQLite database by default
- optional PostgreSQL for deployments that prefer an external relational store
- one local data root
- one bundled web shell

## Design Principles

- **Single-node first**: one machine, one runtime, one operational context
- **Workspace-native**: workspace resolution is part of the core runtime contract
- **SDK-aligned**: `ya-agent-sdk` stays responsible for agent execution primitives
- **Unified execution model**: API requests, schedules, and bridge ingress all create runs through one session model
- **Simple active-state model**: active run state, live delivery, async task tracking, schedules, and bridge coordination stay inside the process
- **Durable and practical**: SQLite is the default durable store, PostgreSQL is an optional backend, and the local filesystem stores large payloads
- **Architecture-first**: this spec defines runtime structure and interaction boundaries; detailed schema work follows implementation

## Section Map

| Section | Document                                                                                 | Topic                                                          |
| ------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| 00      | [00-overview.md](00-overview.md)                                                         | runtime definition, boundaries, top-level architecture         |
| 01      | [01-configuration-and-workspace-provider.md](01-configuration-and-workspace-provider.md) | configuration layers and `WorkspaceProvider` contract          |
| 02      | [02-execution-and-session.md](02-execution-and-session.md)                               | execution flow, session model, continuation, schedules, bridge |
| 03      | [03-storage-and-streaming.md](03-storage-and-streaming.md)                               | SQLite/PostgreSQL, filesystem, memory, and event delivery      |
| 04      | [04-api.md](04-api.md)                                                                   | HTTP API surface and resource grouping                         |
| 05      | [05-web-ui-and-operations.md](05-web-ui-and-operations.md)                               | web shell, runtime operations, schedules, and bridges          |

## Out of Scope

- multi-tenant control plane
- hosted operator portal
- distributed worker pools and multi-region scheduling
- external coordination services for single-node run management
- full database schema freeze before implementation
