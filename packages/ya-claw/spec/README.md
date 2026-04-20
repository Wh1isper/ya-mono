# YA Claw Architecture Spec

YA Claw is a workspace-native single-node runtime built on top of `ya-agent-sdk`.

This spec set focuses on one clear target shape:

- one runtime service
- one PostgreSQL
- one Redis
- one local data root
- one bundled web shell

## Design Principles

- **Single-node first**: one machine, one runtime, one operational context
- **Workspace-native**: workspace resolution is part of the core runtime contract
- **SDK-aligned**: `ya-agent-sdk` stays responsible for agent execution primitives
- **Durable and simple**: PostgreSQL stores durable runtime state, Redis carries live delivery state, local filesystem stores large payloads
- **Architecture-first**: this spec defines runtime structure and interaction boundaries; database details follow implementation

## Section Map

| Section | Document                                                                                 | Topic                                                  |
| ------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 00      | [00-overview.md](00-overview.md)                                                         | runtime definition, boundaries, top-level architecture |
| 01      | [01-configuration-and-workspace-provider.md](01-configuration-and-workspace-provider.md) | configuration layers and `WorkspaceProvider` contract  |
| 02      | [02-execution-and-session.md](02-execution-and-session.md)                               | execution flow, session model, continuation and fork   |
| 03      | [03-storage-and-streaming.md](03-storage-and-streaming.md)                               | PostgreSQL, Redis, filesystem, and event delivery      |
| 04      | [04-api.md](04-api.md)                                                                   | HTTP API surface and resource grouping                 |
| 05      | [05-web-ui-and-operations.md](05-web-ui-and-operations.md)                               | web shell, runtime operations, and deployment baseline |

## Out of Scope

- multi-tenant control plane
- bridge lifecycle and channel gateway design
- hosted operator portal
- distributed worker pools and multi-region scheduling
- full database schema freeze before implementation
