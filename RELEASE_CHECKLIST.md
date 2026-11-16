# Release checks

Use dedicated test mailboxes and disposable sample messages for these checks.
Record the app commit, Python version, dependency lock, build OS, and outcomes.
These are manual acceptance checks, not claims that a release has passed them.

- [ ] Install requirements.lock in a clean Python 3.14 Linux environment; run
      `bash run_tests.sh` and `python -m pip check`.
- [ ] Run the real Tk test under Xvfb and inspect the app at minimum window size,
      with a long report, scrolling, folder selection, and both themes.
- [ ] Log into a personal Microsoft account and, if supported by your registration,
      an organizational account. Verify consent, rejected consent, timeout,
      logout/relogin, and account switching. Repeat for Gmail.
- [ ] Verify exact/contains rules, Any/All, case sensitivity, priorities, multiple
      matches, and fallback rules against known sample messages in both providers.
- [ ] Confirm Preview changes nothing. Apply Mark, Move, and Delete separately and
      together; verify actual mailbox state, selected folder IDs, Gmail labels,
      and Microsoft message references after moving.
- [ ] Use a backlog larger than the cap, including timestamp ties. Repeated
      incremental runs must drain it without skips. Confirm newest scope is capped.
- [ ] Cancel between messages and close during the final message; restart and
      verify the checkpoint and completed actions.
- [ ] Interrupt a request or disconnect the network during an action. Verify the
      recovery report, explicitly resolve uncertainty, and confirm successful
      actions are not repeated, including after a move out of Inbox.
- [ ] Simulate unwritable settings after application. Restore writes and confirm
      recovery commits the checkpoint without repeating mailbox changes.
- [ ] Run `bash build_linux.sh` and `dist/EmailSiftingAgent --check-install`.
- [ ] Launch the executable on a clean supported Linux machine with no source
      checkout or Python environment; verify both logins and the complete flow.
- [ ] Build on the oldest supported glibc target. Document that target with the
      artifact; do not imply all Linux distributions are supported.

Changing scopes or distributing your own OAuth registration can require provider
review or organizational approval. Verify the registrations separately from the
code and never package client secrets or user credentials.
