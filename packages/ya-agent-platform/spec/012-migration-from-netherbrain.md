# 012 Migration From Netherbrain

## Intent

This document maps the `dev/netherbrain` runtime-centered spec into the `ya-agent-platform` platform-centered spec.

The migration keeps the valuable runtime ideas and upgrades the surrounding system model for multi-tenant cloud operation.

## Concept Mapping

| Netherbrain Concept         | YA Agent Platform Concept                              | Migration Direction                              |
| --------------------------- | ------------------------------------------------------ | ------------------------------------------------ |
| single runtime service      | control plane + execution plane                        | split runtime ownership from platform governance |
| homelab user model          | tenant-aware identity and roles                        | add platform, tenant, workspace scopes           |
| workspace                   | tenant-scoped workspace                                | keep the concept and add tenant ownership        |
| preset                      | agent profile + environment profile                    | split cognitive config from execution config     |
| local / sandbox environment | executor kinds and environment profiles                | generalize to hosted and remote runtimes         |
| IM gateway                  | bridge installation + bridge protocol                  | add tenant routing, delivery policy, and health  |
| chat UI                     | unified Web UI                                         | expand to tenant admin and platform admin        |
| single auth token           | OIDC, service tokens, bridge tokens, break-glass admin | add real multi-actor identity                    |
| session DAG                 | immutable session history                              | keep this design and attach scheduler metadata   |

## What Stays

These Netherbrain ideas stay central:

- conversation and immutable session model
- SDK-native execution with resumable state
- event-driven streaming
- async subagents as first-class orchestration
- bridge normalization instead of channel-specific core logic

## What Changes

### 1. Ownership moves from instance to tenant

The original runtime assumed one service owner and lightweight multi-user access.

The platform treats tenant scope as a primary key carried through:

- configuration
- identity
- storage
- scheduling
- bridge routing
- audit

### 2. Execution is scheduled, not assumed local

Netherbrain centered one process and one machine.

YA Agent Platform resolves a target environment profile and schedules the session into a runtime pool.

### 3. Profile design splits behavior from environment

The old preset model mixed model behavior and execution environment.

The new model separates:

- `agent_profile`
- `environment_profile`

This makes one agent usable across several execution environments.

### 4. Web UI becomes a full product surface

Netherbrain Web UI focused on chat with settings.

YA Agent Platform Web UI includes:

- chat experience
- tenant admin console
- platform admin portal

### 5. Multi-tenancy is durable and explicit

Resource ownership, access control, quotas, and support access are modeled directly rather than implied.

## Phased Migration Plan

### Phase 1: preserve runtime semantics inside the platform package

- keep conversation and session semantics aligned with the Netherbrain model
- keep SDK integration and streaming model compatible where practical
- keep bridge normalization patterns

### Phase 2: add tenant-aware storage and auth

- attach `tenant_id` and `workspace_id` to all durable resources
- replace the homelab token model with platform and tenant identity flows
- add role-aware APIs and audit records

### Phase 3: split presets into profiles

- migrate runtime presets into `agent_profiles`
- create `environment_profiles` for local assumptions previously embedded in presets
- update config resolution logic to compose both

### Phase 4: add runtime pools and remote execution

- introduce scheduler, leases, and worker placement
- move local and sandbox assumptions behind executor kinds
- add remote runtime registration for hybrid deployments

### Phase 5: expand Web UI and admin surfaces

- evolve the current chat shell into a role-aware platform UI
- add tenant admin routes and platform admin routes
- expose audit, runtime health, and bridge management in the UI

## Implementation Guidance For This Repository

Within `packages/ya-agent-platform`, build in this order:

1. multi-tenant tables and auth context
2. control-plane CRUD for tenants, workspaces, agent profiles, and environment profiles
3. session orchestration with queue-ready statuses
4. event streaming and durable replay storage
5. bridge installations and normalized bridge APIs
6. Web UI integration for chat and admin surfaces

## Migration Principle

Treat Netherbrain as the execution kernel reference.
Treat YA Agent Platform as the operated product built around that kernel.
