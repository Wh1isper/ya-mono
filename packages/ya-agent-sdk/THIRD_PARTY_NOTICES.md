# Third-party notices

## Agent Foundation SelfHealing

`ya_agent_sdk/agents/models/self_healing.py` and
`ya_agent_sdk/capabilities/foundation/self_healing.py` are adapted from
Converge AI's `agent-foundation`, commit
`e36d0518c51a1d89eef20715de4f3b187040d885`:

- `packages/a13n-harness/a13n_harness/models/self_healing.py`
- `packages/a13n-harness/a13n_harness/models/capability.py`

Copyright 2026 Converge AI. Licensed under Apache License 2.0; see
`LICENSE-APACHE-2.0` in this distribution.

YA modifications isolate repairs on a copied request history, use native Pydantic AI
prompt metadata, and install the model through the explicit runtime foundation and
portable capability catalog. All five upstream default recovery rules are retained.
