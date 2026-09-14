# Email Sifting Agent

A desktop app for organizing a Microsoft inbox using configurable rules.

## Running a sift

Login and Microsoft Graph operations run on a background worker so the window
stays responsive. Click Go to fetch emails and watch the progress counter.
Cancel stops after the current request/message finishes; actions already applied
remain, and an interrupted run does not advance the checkpoint. A retry can
revisit messages changed before interruption. If the final message has already
finished, the run completes normally.

Rules and settings are captured when a run starts. Edits made while it is running
apply to the next run. Go and Log out are disabled until the current sift ends.
Closing the window requests cancellation and waits for the active operation to
finish; browser login may need to finish or time out first.

## Offline tests

From the project directory, run:

```bash
bash run_tests.sh
```

This runs the full test suite followed by the fake-inbox simulation, stopping if
either fails. It uses `.venv/bin/python` when available, otherwise `python3`.
You can pass simulator options, such as `bash run_tests.sh --emails path/to/inbox.json`.

The suite uses Python's built-in `unittest`, fake emails, and a recording Graph
substitute. It needs no Microsoft login, network connection, or running GUI.
Settings tests use temporary directories; your saved rules and checkpoint are
not changed.

Coverage includes matchers, case sensitivity, Any/All conditions, action payloads,
priority, multiple matching rules, fallback rules, deletion ordering, failures,
settings persistence, pagination, timestamp ties, and checkpoint preservation.
It also checks background thread/callback separation, login submission,
progress reporting, cancellation boundaries, and settings edits during a run.
These tests do not validate actual Graph server behavior, browser authentication,
or visual widget interactions.

For a fresh environment, install the app dependencies first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Try rules against fake emails

Run the real rule engine against an editable sample inbox:

```bash
.venv/bin/python -m tests.simulate
```

This reads `app/user/useroptions.json` and `tests/fixtures/inbox.json`, then prints
the actions each matching email would receive and the IDs of unchanged emails.
All actions are recorded locally in memory, including Delete and Move.

Edit the sample inbox to try different subjects, senders, and bodies. Each record
needs a unique `id`; optional fields are `subject`, `sender`, `body`, and
`received_at` (an ISO timestamp). For example:

```json
[
  {
    "id": "test-invoice",
    "subject": "Invoice for September",
    "sender": "billing@example.com",
    "body": "Payment due Friday."
  }
]
```

To test the rules saved through the app instead of the bundled defaults:

```bash
.venv/bin/python -m tests.simulate --rules "$HOME/.config/EmailSiftingAgent/useroptions.json"
```

You can also supply `--emails path/to/inbox.json` and `--rules path/to/options.json`.
The simulator reads these files without changing them. It applies rules to every
supplied fake email; fetching limits and checkpoints are covered by the automated
checkpoint tests separately. The Graph substitute records requests but does not
emulate server-side changes to message IDs after moves.

To run only one test module:

```bash
.venv/bin/python -m unittest tests.test_processing -v
```
