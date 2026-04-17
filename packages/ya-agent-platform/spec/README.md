# YA Agent Platform Specs

This directory is the source of truth for the `ya-agent-platform` target architecture.

The spec starts from the ideas proven in `dev/netherbrain`, then rebuilds them for a cloud-ready, multi-tenant platform with a first-party Web UI, tenant administration, platform administration, and environment-aware agent execution.

## Design Position

`ya-agent-platform` is designed around these defaults:

- multi-tenant from day one
- cloud deployment as the primary operating model
- first-party Web UI for chat, tenant admin, and platform admin
- control plane and execution plane separation
- environment-aware scheduling so agents can run in different runtime environments
- durable storage and message fan-out through PostgreSQL, Redis, and object storage
- `ya-agent-sdk` as the execution substrate for agent behavior, tools, state restore, and streaming

## Document Order

01. [`000-platform-overview.md`](000-platform-overview.md) — goals, scope, terminology, and system context
02. [`001-product-model.md`](001-product-model.md) — product surfaces, personas, and resource hierarchy
03. [`002-multi-tenancy-and-identity.md`](002-multi-tenancy-and-identity.md) — tenant model, roles, authn, authz, and isolation
04. [`003-control-plane.md`](003-control-plane.md) — control-plane responsibilities, config resolution, and policy model
05. [`004-runtime-and-environments.md`](004-runtime-and-environments.md) — runtime pools, environment profiles, and execution environments
06. [`005-session-and-execution-model.md`](005-session-and-execution-model.md) — conversation, session, async execution, and lifecycle
07. [`006-events-streaming-and-notifications.md`](006-events-streaming-and-notifications.md) — event protocol, transports, fan-out, and notifications
08. [`007-bridge-protocol.md`](007-bridge-protocol.md) — normalized bridge contract for external channels
09. [`008-http-api.md`](008-http-api.md) — API families and initial endpoint surface
10. [`009-web-ui.md`](009-web-ui.md) — first-party Web UI for chat, tenant admin, and platform admin
11. [`010-deployment-topology.md`](010-deployment-topology.md) — deployment modes, regions, scaling, and operations
12. [`011-data-model.md`](011-data-model.md) — durable storage model and entity relationships
13. [`012-migration-from-netherbrain.md`](012-migration-from-netherbrain.md) — migration mapping from Netherbrain concepts to YA Agent Platform

## Reading Paths

### Product and architecture

Read in order from `000` to `005`, then `009` and `010`.

### API and integration

Read `006`, `007`, `008`, and `011`.

### Migration planning

Read `012` after `000` through `005`.

## Build Principle

Implementation should land in this order:

1. durable multi-tenant data model
2. tenant-aware auth and policy enforcement
3. control-plane APIs for tenants, workspaces, profiles, and bridges
4. conversation and session orchestration backed by runtime pools
5. Web UI shells for chat and admin surfaces
6. bridge ingestion and outbound delivery
7. multi-region and remote-runtime expansion

## Core Shift From Netherbrain

Netherbrain described a strong single-instance runtime service.

YA Agent Platform keeps the good parts:

- immutable session-oriented execution history
- normalized events and streaming
- SDK-native execution and restore
- chat and bridge delivery as first-class concerns

YA Agent Platform adds the missing platform layers:

- explicit tenant boundary
- platform admin and tenant admin surfaces
- environment profiles and runtime pool scheduling
- cloud deployment and remote execution support
- shared policy, secrets, quotas, and audit controls
