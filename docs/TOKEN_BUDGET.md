# Token budget enforcement

Each admitted turn reserves a conservative estimate of the complete provider prompt and a bounded completion allowance while holding the daily usage row lock. The reservation is recorded in `reserved_tokens_today`, so concurrent requests cannot oversubscribe the remaining budget. OpenRouter receives the resulting completion ceiling through `max_tokens`.

Successful calls reconcile the reservation to actual prompt plus completion usage and increment `tokens_today`. A failure before provider execution releases both reservations. An uncertain provider failure keeps the reservation, which is the safe outcome when billing cannot be established.

The invariant is enforced again during reconciliation: a transaction that would move `tokens_today` above `MAX_TOKENS_PER_DAY` is rejected and rolled back.

Saved-chat estimation and generation use the conversation's stored persona_id.
The backend resolves one registry object and fetches one Docs context, then passes
that exact context to generation. Cache refresh cannot switch prompts between
estimation and the provider call. Temporary chats retain legacy Odin context.
