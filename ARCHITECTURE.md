# Architecture

The Tk pages submit authentication and sifting to `BackgroundWorker`. The worker
owns the async loop; UI callbacks run on Tk's thread.

`EmailAgent` (`app/agents/base.py`) is the abstract mailbox template. Providers
implement authentication, logout, inbox fetching, deletion, moving, and marking.
The rule engine uses these methods without constructing SDK requests.

`MicrosoftGraphAgent` wraps the Microsoft Graph SDK. Existing authentication and
paging helpers in `app/microsoftGraph/email.py` remain available for compatibility.
`as_agent` wraps legacy raw Graph clients at the public boundary.

The sifting service fetches through the provider contract, computes a checkpoint
before actions can change message IDs, and runs the shared rule engine. Only a
successful run returns checkpoint changes for the UI to persist. Cancellation
is checked between requests/messages; all actions for a started message finish.

Provider messages expose the same fields used by matchers: `id`, `subject`,
`from_.email_address.address`, `body.content`, and UTC `received_date_time`.
Fetch implementations must preserve timestamp ties across capped batches and
exclude previously processed IDs at the inclusive oldest-first boundary.

`GmailAgent` wraps Google's Gmail API with personal-account browser OAuth and
session-only credentials. It decodes raw MIME using Python's email parser into
the shared message shape. Its synchronous SDK calls run on the background worker,
as do Microsoft authentication calls. Cancellation is checked around each fetch.
Gmail has no oldest-first listing, so all candidate pages are fetched and sorted
before applying the batch limit. Large inboxes therefore require more requests.

Rules and preferences remain shared. Providers expose a `mailbox_key` after
authentication (Microsoft home-account ID or Gmail address, prefixed by provider).
Login preserves the checkpoint only for the same mailbox key. Switching accounts
or migrating from legacy unscoped settings resets it so one account cannot skip
another account's mail. The application controller holds an `email_agent`.
Gmail maps folder moves to user labels plus removal of INBOX, deletion to Trash,
and importance to the binary IMPORTANT label. See README for setup and semantics.
