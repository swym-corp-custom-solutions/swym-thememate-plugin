# Telemetry

Every ThemeMate session records its state via `telemetry_state.py`, run
silently (no output shown to the user). This file is the single source of
truth for the field list and the update rules -- other reference files only
note *when*, in their own workflow context, a call should fire, and link
back here for the mechanics.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" set --mode <ask|inspect|edit> [--feature "<Wishlist Plus|Save For Later|Back In Stock|Recently Viewed|B2B List>"] [--usecase "<one-line paraphrase of the ask>"] [--role <internal|agency|merchant|support>] [--store "<store domain/URL as given>"] [--summary "<summary>"] [--outcome <completed|blocked|error|scope_rejected>] [--usecase-met <yes|no>] [--failure-category "<short category>"]
```

`--agency` and `--demo-store` are set via their own standalone calls (see
below) rather than in the flags above. A call only updates the fields it's
given -- omit anything you don't have a value for yet.

## Field reference

| Field | Values | Meaning | Normally first set by |
|---|---|---|---|
| `--mode` | `ask` / `inspect` / `edit` | Classification from SKILL.md Section 2 | SKILL.md, on first message |
| `--feature` | Wishlist Plus / Save For Later / Back In Stock / Recently Viewed / B2B List | Which Swym product the session is about | SKILL.md, on first message |
| `--usecase` | one-line paraphrase | The user's underlying ask, not the outcome | SKILL.md, on first message |
| `--role` | `internal` / `agency` / `merchant` / `support` | Who's driving the session -- `support` = swym_internal+Support, `internal` = swym_internal+Success/ACQ | [roles.md](roles.md)'s identification logic |
| `--agency` | agency name | Only for `agency` role | [roles.md](roles.md) |
| `--store` | domain/URL as given, later the resolved `.myshopify.com` handle | The store in scope | SKILL.md first call (raw value), overwritten by [shopify-workflow.md](shopify-workflow.md)'s Prerequisites step (resolved handle) |
| `--demo-store` | `.myshopify.com` handle | A substitute store used when the real theme isn't reachable, kept separate from `--store` | [shopify-workflow.md](shopify-workflow.md) |
| `--summary` | short string, under ~400 chars | What's happened in the session so far, for a human scanning the dashboard | SKILL.md, updated repeatedly -- see "Updating `--summary`" below |
| `--outcome` | `completed` / `blocked` / `error` / `scope_rejected` | How the session ended | SKILL.md, at the final stopping-point call |
| `--usecase-met` | `yes` / `no` | Whether the original ask was actually satisfied -- independent of `--outcome` (a session can complete technically without satisfying the use case, or vice versa) | SKILL.md, at the final stopping-point call |
| `--failure-category` | short label, e.g. `no_theme_access`, `platform_not_shopify`, `missing_prerequisite`, `plan_declined`, `api_unclear` | Only set when `--outcome` isn't `completed`. Reuse an existing category over inventing a near-duplicate | SKILL.md, at the final stopping-point call |

## When to call

**First consolidated call.** As soon as you've finished reading the user's
first message and classified mode -- before any investigation or tool use --
set every field you already know: `--mode`, `--feature`, `--usecase`,
`--role` (omit it if resolution is still pending, e.g. mid-way through the
swym_internal team question -- follow up with a `--role`-only call once
it's answered), and `--store` whenever the user names or you otherwise
discover a store domain/URL anywhere in that first message, regardless of
platform or mode -- use the raw value as given, even an unresolved custom
domain. Don't spread mode/feature/usecase across multiple early calls -- get
them all into this one.

Include an interim `--summary` in that same first call: a one-line statement
of what you're doing in response to the ask (e.g. "Checking whether the
wishlist grid is Swym's default UI or a custom build"), not an outcome.

**Late-resolving fields.** If role, agency name, or the resolved store
handle become known after the first call, send a standalone call for just
that field -- a call only updates the fields it's given, so this doesn't
conflict with what's already stored. The store-handle overwrite (raw
domain/URL -> resolved `.myshopify.com` handle) is expected and described in
[shopify-workflow.md](shopify-workflow.md); `--demo-store` is always its own
separate field, set only when shopify-workflow.md's "if Pull fails" path is
taken.

**Updating `--summary`.** Send another `--summary` update at the end of
**every** turn -- whenever it reaches a natural pause (an answer given, a
plan presented, a question asked back) -- not just the first one, so the
dashboard reflects where the session actually is instead of freezing after
turn one.

`--summary` replaces, it doesn't append -- `telemetry_state.py` overwrites
the stored value with whatever you send, there's no code-side accumulation.
**Every one of these updates -- interim, end-of-turn, final -- must restate
the whole session so far, not describe only the turn that just happened.**
A summary of just the latest turn silently erases everything earlier the
moment it's sent. Before writing it, mentally recap all prior turns plus
what just happened, then condense that into one short, simple sentence --
a plain restatement of where the session stands, not a recap of every
turn's detail. Treat 400 characters as a hard backstop you should never
approach, not a target to write up to -- the telemetry server rejects the
entire event outright if `summary` runs longer, so a long one doesn't just
get cut off, it silently drops that whole update (mode/outcome/etc
included). `telemetry_state.py` also trims to 400 bytes as a last-resort
safety net, but don't rely on it -- write short in the first place.

`--summary` is what actually happened or was resolved, for a human scanning
the dashboard -- distinct from `--usecase`, which paraphrases the ask
itself, not the outcome.

**Updating `--usecase`.** Only changes when the use case itself changes. A
session can have several turns, mode transitions, or even multiple
`/thememate` invocations that are all still the same underlying ask (a
follow-up question, a plan confirmation, "continue," an inspect that turns
into an edit of the same thing) -- none of those are a new use case, so
don't re-issue `--usecase` for them. Before writing one, `get` the current
value first; only overwrite it when the user has actually pivoted to a
materially different goal or question than what's stored, and pass the new
one-line paraphrase in that case.

**Final stopping-point call.** When the task reaches a stopping point
(done, blocked, hit an error, or rejected as out of scope by SKILL.md
Section 3's platform gate), send one last call carrying `--outcome`,
`--usecase-met`, `--failure-category` (if not `completed`), and the final
`--summary` -- all in that same call, not a separate end-of-turn `--summary`
update first.
