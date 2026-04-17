# YA Agent Platform Specs

This directory is the source of truth for the `ya-agent-platform` target architecture.

The spec starts from the ideas proven in `dev/netherbrain`, then rebuilds them for a cloud-ready, multi-tenant platform with a first-party Web UI, an admin surface, a single configurable `WorkspaceProvider`, and environment-aware agent execution.

## Design Position

`ya-agent-platform` is designed around these defaults:

- multi-tenant from day one
- cloud deployment as the primary operating model
- first-party Web UI for chat and administration
- control plane and execution plane separation
- environment-aware scheduling so agents can run in different runtime environments
- durable storage and message fan-out through PostgreSQL, Redis, and object storage
- `ya-agent-sdk` as the execution substrate for agent behavior, tools, state restore, and streaming
- tenants as isolation boundaries
- cost centers as the primary budgeting and reporting grouping
- one service instance supports one `WorkspaceProvider`
- business-specific conversation and project composition stays above the platform layer

## Document Order

01. [`000-platform-overview.md`](000-platform-overview.md) — goals, scope, terminology, and system context
02. [`001-product-model.md`](001-product-model.md) — product surfaces, personas, and resource hierarchy
03. [`002-multi-tenancy-and-identity.md`](002-multi-tenancy-and-identity.md) — tenant isolation, admin/user model, authn, authz, and cost-center attribution
04. [`003-control-plane.md`](003-control-plane.md) — control-plane responsibilities, config resolution, and policy model
05. [`004-runtime-and-environments.md`](004-runtime-and-environments.md) — runtime pools, environment profiles, and `WorkspaceProvider`-driven execution environments
06. [`005-session-and-execution-model.md`](005-session-and-execution-model.md) — conversation, session, project binding, async execution, and lifecycle
07. [`006-events-streaming-and-notifications.md`](006-events-streaming-and-notifications.md) — event protocol, transports, fan-out, and notifications
08. [`007-bridge-protocol.md`](007-bridge-protocol.md) — normalized bridge contract for external channels
09. [`008-http-api.md`](008-http-api.md) — API families and initial endpoint surface
10. [`009-web-ui.md`](009-web-ui.md) — first-party Web UI for chat and administration
11. [`010-deployment-topology.md`](010-deployment-topology.md) — deployment modes, regions, scaling, and operations
12. [`011-data-model.md`](011-data-model.md) — durable storage model and entity relationships

## Reading Paths

### Product and architecture

Read in order from `000` to `005`, then `009` and `010`.

### API and integration

Read `006`, `007`, `008`, and `011`.

## Build Principle

Implementation should land in this order:

1. durable multi-tenant data model
2. admin and user identity with scoped grants
3. control-plane APIs for tenants, cost centers, profiles, bridges, and provider-facing config
4. conversation and session orchestration backed by runtime pools and `WorkspaceProvider`
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

- explicit tenant boundary for isolation
- admin and user surfaces under one product
- cost centers for budgets, quotas, and usage attribution
- a pluggable `WorkspaceProvider` abstraction for project-to-environment mapping
- cloud deployment and remote execution support
- shared policy, secrets, quotas, and audit controls
