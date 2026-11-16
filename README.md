# Email Sifting Agent

A Linux desktop app that organizes Microsoft and personal Gmail inboxes using
editable rules. New installations have no rules and perform no mailbox changes
until you preview and apply a batch.

## Install and run

The tested target is **Linux with Python 3.14** and Tk/Tcl. Install your distro's
Tk package if `python3 -m tkinter` is unavailable. The Linux executable must be
built on the oldest Linux distribution you intend to support; a build made on a
newer system may require newer glibc. Other platforms are not currently supported
by the recovery file lock.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python appROOT.py
```

`requirements.lock` pins the complete tested development/build environment,
including transitive dependencies. `requirements.txt` contains runtime bounds;
`requirements-dev.txt` adds packaging tools. Re-resolve the lock in a fresh
Python 3.14 environment after intentionally updating those bounds, then run the
suite, GUI test, and build checks before committing it.

Settings are in `~/.config/EmailSiftingAgent/useroptions.json`. Override the data
directory with `EMAIL_SIFTING_DATA_DIR` for isolated testing. Invalid settings are
reported without overwriting your file. Back up and repair the file if startup
reports an error. Schema version 1 is supported; older settings without an
explicit version remain accepted if their contents are valid. Empty keyword
rules must be repaired before they can run.

## Connect Microsoft

The app uses an interactive public-client login with delegated `Mail.ReadWrite`.
The bundled client ID is configurable: set `MICROSOFT_CLIENT_ID` to your Entra
application ID and optionally `MICROSOFT_TENANT_ID` (default `common`). For your own
registration:

1. Register an application in Microsoft Entra. Choose account types that include
   personal Microsoft accounts if you want Outlook.com support.
2. Add the **Mobile and desktop applications** platform and configure the loopback
   redirect `http://localhost:8400`.
3. Add delegated Microsoft Graph `Mail.ReadWrite` permission. Tenant policy may
   require administrator consent. No client secret belongs in this desktop app.
4. Set the environment variables before starting the app, then choose Microsoft.

See the [Microsoft desktop registration guide](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-registration).
The Entra registration is external configuration and cannot be checked by the
offline tests.

Both providers now keep tokens in memory for the session. There is no automatic
Microsoft login or new persistent token cache. Sign out closes the app's client
and credentials; it does not revoke account consent or sign out your browser.
Legacy authentication records are removed on Microsoft sign out. Persistent token
caches created by older versions are no longer read, but are not automatically
erased; remove those separately if upgrading. Browser authentication waits up to
180 seconds. Closing during login waits for that operation to end.
Login and mailbox requests use the same CAE token cache mode. Preview never
starts an interactive login; if silent renewal is unavailable, the app asks you
to log out and log in again instead of opening a second browser flow.

Microsoft requests immutable message IDs. The first Microsoft login after this
upgrade resets the old checkpoint once because earlier IDs used a different
format. Moving messages within the mailbox then preserves recovery references.

## Connect Gmail

Enable the Gmail API in a Google Cloud project and create a Desktop OAuth client
following the [Google Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).
For a personal account, configure an External audience and add yourself as a test
user while the OAuth app is in testing. Download the client JSON and select it
using **Choose Gmail client JSON...**, then choose **Log in with Gmail** and
approve `gmail.modify`. The selection lasts for the current app session. For a
default on future launches, save the JSON to
`~/.config/EmailSiftingAgent/gmail-client.json`, or set `GMAIL_CLIENT_SECRET_FILE`
to its path. A file selected in the app takes precedence over these defaults.

Authentication opens your browser and temporarily listens at
`http://localhost:<available-port>/` for Google's callback. The Google SDK starts
and closes this endpoint during login; it is not a permanent web API route.
Use a **Desktop app** OAuth client, which supports the available loopback port,
rather than a Web application client with a fixed redirect URI. Google's
authorization and token endpoints come from the downloaded JSON's `auth_uri`
and `token_uri` fields. Missing fields are reported before opening the browser.

Gmail Delete moves to Trash. Move selects an existing user label, adds it, and
removes INBOX; Archive only removes INBOX. Other labels remain attached. High
importance sets IMPORTANT; Normal and Low both clear it. Read/Unread controls
UNREAD. Rules are shared between providers, so review destinations when switching.

Gmail's [documented newest-first listing](https://developers.google.com/workspace/gmail/api/guides/list-messages)
lets the app select a capped batch before downloading MIME bodies. Oldest-first
still lists all candidate ID pages, but downloads minimal metadata and raw bodies
only for the selected messages (plus metadata for any excluded time-boundary
candidates). Newest-first stops paging once its batch is filled. Exact timestamp
checks and saved IDs preserve ties across batches.

## Preview and apply

1. Add rules on **Rules**. Lower priorities run first. Multiple matching rules
   run until a Delete action; actions within each rule run Mark, Move, then Delete.
   Default is an explicit fallback for messages that match no normal rule.
   New rules start with no actions. Use **Add Mark**, **Add Move**, or **Add Delete**
   to display that action's settings, and **Remove Mark/Move/Delete** to remove it.
   Mark lets you choose Read/Unread or an importance level and explains the result.
2. Use **Refresh folders / labels** to reload destinations. Move uses a selection
   list. All pending destinations are checked before any mailbox modification.
3. Choose the scope and click **Preview**. Inspect message subjects, rules,
   actions, and settings on **Results**. Preview makes no mailbox changes and
   does not advance the checkpoint.
4. Return to **Sift** and click **Apply preview**. The reviewed action list is
   frozen; edits to rules apply to your next preview. Progress and outcomes appear
   in Results. You can export the report as JSON.

The incremental scope processes the oldest unprocessed messages, up to the limit
(1–10000). The newest scope reprocesses only the newest capped batch, not every
message in a large inbox. Checkpoints belong to the authenticated mailbox;
switching accounts resets the checkpoint, while recovery batches remain separate.

Cancel stops between messages or fetch requests. All actions for a started
message finish unless an action fails. Completed changes remain. Closing drains
completion callbacks before destroying the window, so a successful batch still
saves its checkpoint. Provider requests already in flight must finish first.

## Recover an interrupted batch

The app saves the reviewed batch before the first modification and saves each
action outcome. Preview again after a failure or cancellation to inspect that
same batch. Its original rules remain frozen even if you edited the current
rules. Apply resumes pending actions and skips completed ones, including actions
on a message already moved out of Inbox. Recovery must finish before a new batch
can run for that mailbox.

An action is recorded as **uncertain** before its request begins. A crash or
request error can therefore leave uncertainty about whether the server applied
the change. The app will not automatically replay it. Inspect the message in the
provider, select the action in Results, and choose either **Retry selected
uncertain action** or **Mark selected action completed**. Then apply the remaining
preview. For an uncertain Move, immutable Microsoft IDs and stable Gmail IDs keep
the recovery reference valid. If you manually deleted the message or made other
changes, inspect every remaining action before proceeding.

If a destination no longer exists, Preview still displays the interrupted batch
and reports the failed destination check. Restore the destination, or perform the
pending action manually and mark it completed in Results before resuming. This
completion control also works for pending actions in an existing recovery batch.

The checkpoint is committed only after every action completes. If saving it
fails, the completed batch stays available so another attempt saves the
checkpoint without repeating changes. The last completed report and active
recovery record live under the data directory's `runs/` folder. They contain
message IDs, subjects, rule names, action settings, and errors; no message bodies
or credentials. Files use owner-only permissions. Preserve recovery records when
troubleshooting. A file lock prevents simultaneous processing of one mailbox.
Automatic Graph request retries are disabled so an ambiguous mutation reaches
the recovery flow rather than being silently repeated by the transport.

## Tests and packaging

```bash
bash run_tests.sh
.venv/bin/python -m pip check
EMAIL_AGENT_GUI_TESTS=1 xvfb-run -a .venv/bin/python -m unittest tests.test_gui_smoke -v
bash build_linux.sh
dist/EmailSiftingAgent --check-install
```

Both scripts use `.venv/bin/python` when present, otherwise `python3`. Set
`EMAIL_AGENT_PYTHON` to use another interpreter. The suite uses temporary settings,
fake mailboxes, and mocked SDK calls; no provider login or network is required.
The GUI test uses actual Tk widgets under a virtual display. CI runs the suite,
GUI test, dependency check, Linux build, and bundled installation check.

Try the real engine against the editable sample inbox without mailbox writes:

```bash
.venv/bin/python -m tests.simulate
.venv/bin/python -m tests.simulate --rules "$HOME/.config/EmailSiftingAgent/useroptions.json"
```

The simulator accepts `--emails path/to/inbox.json`. Each record needs a unique
`id`; optional fields are `subject`, `sender`, `body`, and ISO `received_at`.
It does not change the input files, settings, or checkpoints.

Before distributing a release, follow [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
with dedicated test accounts. Offline tests cannot prove browser login, consent,
provider-side moves/deletes, or compatibility on another Linux installation.
