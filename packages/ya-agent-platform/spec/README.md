# YA Agent Platform Specs

This directory is the source of truth for the initial platform build.

## Document Order

1. [`000-platform-overview.md`](000-platform-overview.md) — goals, scope, terminology
2. [`001-system-architecture.md`](001-system-architecture.md) — component model and deployment topology
3. [`002-bridge-contract.md`](002-bridge-contract.md) — normalized bridge protocol for IM adapters
4. [`003-http-api.md`](003-http-api.md) — first API surface for backend and web integration

## Build Principle

The platform grows in this order:

1. define contracts
2. land minimal executable surfaces
3. connect persistence and runtime orchestration
4. add bridge implementations and production controls
