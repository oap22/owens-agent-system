# Unattended local operations

This mode is for a preauthorized, bounded local job. It does not create a schedule. Before using it, an operator must audit inherited MCP servers, hooks, project config, and environment; this launcher does not isolate them.

Require a task contract naming the owner, exact writable scope, allowed actions, acceptance criteria, maximum iterations/time, idempotency key, retry limit, and notification trigger. No sends, purchases, remote mutations, merges, or note deletion. When a required permission, credential, source, or account is missing, record one blocker and stop. Do not loosen policy or retry endlessly. Preserve the last successful cursor until processing commits successfully. A scheduler should call a specific owned skill, not an open-ended "improve everything" prompt.
