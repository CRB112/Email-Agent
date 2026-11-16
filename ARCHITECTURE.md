# Architecture

Tk pages submit work to `BackgroundWorker`, which owns a persistent asyncio loop.
Only Tk callbacks update widgets. Authentication, destination discovery, sifting,
and logout run on that worker. Registered provider sessions are closed on worker
shutdown; Tk continues draining completions until shutdown finishes.

`EmailAgent` abstracts authentication, fetching, destinations, delete, move, mark,
and session cleanup. `MicrosoftGraphAgent` owns an explicit Graph HTTP client and
session-only Azure credential. `GmailAgent` owns a session-only Google client.
Legacy raw Graph clients are wrapped by `as_agent` at the public boundary.

`validation.py` validates settings on load/save, editor submission, and planning.
Missing sender parts normalize to an empty address. Keyword matchers reject empty
or blank lists. Default remains an explicit unmatched-message fallback.

`execution.plan_actions` evaluates rules against the fetched snapshot and freezes
per-message action lists. Delete terminates planning for that message. Preview
returns those lists without mailbox writes or checkpoint changes. Apply uses the
same lists, validates pending destinations, then executes the frozen actions.
Edits made during a run are preserved when checkpoint fields are merged later.

`RunJournal` stores one active batch per mailbox using atomic replacement, fsync,
owner-only files, and an advisory Linux file lock. Each request transitions from
pending to uncertain before dispatch, then to done after success. Uncertain
requests require explicit review rather than automatic replay. Recovery keeps
current message IDs after moves, skips done actions, and finishes the original
batch even when its messages no longer appear in Inbox. A successful result is
retained until the Tk callback saves settings and acknowledges the journal. The
last completed batch also invalidates stale previews from other windows.

Provider messages expose id, subject, from_.email_address.address, body.content,
and UTC received_date_time. Fetches preserve timestamp ties across capped batches
using inclusive lower boundaries and processed IDs. Checkpoints are computed
before mailbox mutations. Microsoft requests immutable IDs and migrates legacy
checkpoint IDs once. Gmail uses its documented newest-first order: reverse all
candidate ID pages for oldest-first; stop early for newest-first. Only selected
messages receive MIME body downloads, after minimal metadata boundary checks.

Rules and preferences are shared; checkpoints and recovery are scoped to mailbox
identity. Journal reports retain subjects, IDs and action settings, never bodies
or credentials. Cancel stops at safe message/request boundaries. No automatic
application-level retry is performed for an uncertain mutation.
