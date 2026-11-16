"""Main application page and its notebook tabs."""

import tkinter as tk
from tkinter import filedialog, messagebox
import json
from threading import Event

import ttkbootstrap as ttk
from azure.identity import AuthenticationRequiredError

from app.services.sifting import sift
from app.services.control import SiftCancelled
from app.parser.parser import (
    loadUserOptions,
    saveUserOptions,
)
from app.rules.definitions import create_rule_template
from app.widgets.rule_card import RuleCard
from app.widgets.rule_editor import RuleEditor
from app.widgets.scrollable_frame import ScrollableFrame


def error_text(error):
    cause = error
    while cause is not None:
        if isinstance(cause, AuthenticationRequiredError):
            return "Your Microsoft session needs a fresh login. Log out, then log in again"
        cause = cause.__cause__
    return str(error)


class MainPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.sifting = False
        self.cancel_event = Event()
        self.preview_result = None
        self.destinations = {}
        self.latest_records = []
        self.result_rows = {}
        self.loading_destinations = False
        self.sift_mode = tk.StringVar(value="since_last")
        self.max_emails = tk.StringVar(value="100")
        self.dark_mode = tk.BooleanVar(value=self._saved_dark_mode())

        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, padx=16, pady=16)

        self.sift_tab = ttk.Frame(self.notebook)
        self.rules_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.results_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.sift_tab, text="Sift")
        self.notebook.add(self.rules_tab, text="Rules")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.results_tab, text="Results")

        self._build_logout_button()
        self._build_sift_tab()
        self._build_rules_tab()
        self._build_settings_tab()
        self._build_results_tab()

        self.refresh_rules()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_logout_button(self):
        self.logout_button = ttk.Button(
            self,
            text="Log out",
            command=self.logout,
            bootstyle="danger outline",
            padding=(10, 2),
        )
        self.logout_button.place(relx=1.0, x=-26, y=19, anchor="ne")

    def _build_sift_tab(self):
        ttk.Label(
            self.sift_tab,
            text="Sift your inbox",
            font=("Mouldy Cheese", 30),
            bootstyle="primary",
        ).pack(pady=(48, 8))

        ttk.Label(
            self.sift_tab,
            text="Choose which messages to process, then run your rules.",
            bootstyle="secondary",
        ).pack(pady=(0, 24))

        scope = ttk.LabelFrame(
            self.sift_tab,
            text="Emails to sift",
            padding=(12, 8),
        )
        scope.pack()
        ttk.Radiobutton(
            scope,
            text="Only emails received since the last successful sift",
            variable=self.sift_mode,
            value="since_last",
        ).pack(anchor="w")
        ttk.Radiobutton(
            scope,
            text="Newest emails again (up to the configured limit)",
            variable=self.sift_mode,
            value="all",
        ).pack(anchor="w")

        self.last_sift_label = ttk.Label(self.sift_tab, text="")
        self.last_sift_label.pack(pady=(8, 0))
        self._refresh_sift_options()

        self.go_button = ttk.Button(
            self.sift_tab,
            text="Preview",
            command=self.attempt_go,
            bootstyle="success",
            padding=(34, 10),
        )
        self.go_button.pack(pady=(20, 8))
        self.apply_button = ttk.Button(
            self.sift_tab, text="Apply preview", command=self.apply_preview,
            state="disabled", bootstyle="warning", padding=(20, 8),
        )
        self.apply_button.pack(pady=(0, 8))
        self.cancel_button = ttk.Button(
            self.sift_tab, text="Cancel", command=self.cancel_sift,
            state="disabled", bootstyle="secondary outline",
        )
        self.cancel_button.pack(pady=(0, 8))
        self.progress = ttk.Progressbar(self.sift_tab, length=360)
        self.progress.pack(pady=(0, 8))

        self.status = ttk.Label(
            self.sift_tab,
            text="",
            justify="center",
            wraplength=540,
        )
        self.status.pack()

    def _build_rules_tab(self):
        heading = ttk.Frame(self.rules_tab)
        heading.pack(fill="x", padx=30, pady=(40, 18))

        ttk.Label(
            heading,
            text="Rules",
            font=("Mouldy Cheese", 30),
            bootstyle="primary",
        ).grid(row=0, column=0, sticky="w")

        email_limit = ttk.Frame(heading)
        email_limit.grid(row=0, column=1, sticky="e")
        ttk.Label(email_limit, text="MAX emails per sift:").grid(
            row=1, column=0, sticky="e"
        )
        ttk.Entry(
            email_limit,
            textvariable=self.max_emails,
            width=8,
        ).grid(row=1, column=1, padx=(8, 6))
        self.max_emails_status = ttk.Label(email_limit, text="")
        self.max_emails_status.grid(row=0, column=2, sticky="s")
        ttk.Button(
            email_limit,
            text="Save",
            command=self.save_max_emails,
            bootstyle="secondary outline",
        ).grid(row=1, column=2)

        ttk.Button(
            heading,
            text="Add rule",
            command=self.show_new_rule_editor,
            bootstyle="primary",
        ).grid(row=1, column=1, sticky="e", pady=(10, 0))
        self.destinations_button = ttk.Button(
            heading, text="Refresh folders / labels", command=self.refresh_destinations,
            bootstyle="secondary outline",
        )
        self.destinations_button.grid(row=1, column=0, sticky="w", pady=(10, 0))

        heading.grid_columnconfigure(1, weight=1)

        rules_box = ttk.LabelFrame(
            self.rules_tab,
            text="Configured rules",
            padding=8,
        )
        rules_box.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        self.rules_list = ScrollableFrame(rules_box)
        self.rules_list.pack(fill="both", expand=True)

    def _build_settings_tab(self):
        ttk.Label(
            self.settings_tab,
            text="Settings",
            font=("Mouldy Cheese", 30),
            bootstyle="primary",
        ).pack(pady=(70, 20))

        ttk.Label(
            self.settings_tab,
            text="Personalize how the application looks and behaves.",
            bootstyle="secondary",
        ).pack(pady=(0, 24))

        appearance = ttk.LabelFrame(
            self.settings_tab,
            text="Appearance",
            padding=20,
        )
        appearance.pack(fill="x", padx=80)

        ttk.Label(
            appearance,
            text="Dark mode",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            appearance,
            text="Use a darker color palette throughout the application.",
            bootstyle="secondary",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        ttk.Checkbutton(
            appearance,
            variable=self.dark_mode,
            command=self.toggle_dark_mode,
            bootstyle="success round toggle",
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(20, 0))

        appearance.grid_columnconfigure(0, weight=1)

    @staticmethod
    def _saved_dark_mode():
        try:
            return bool(loadUserOptions().get("dark_mode", False))
        except Exception:
            return False

    def toggle_dark_mode(self):
        enabled = bool(self.dark_mode.get())
        options = loadUserOptions()
        options["dark_mode"] = enabled
        saveUserOptions(options)

        theme = "darkly" if enabled else "flatly"
        self.controller.style.theme_use(theme)
        self.rules_list.sync_theme()

    def _on_tab_changed(self, _event):
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        if selected_tab == "Rules":
            self.refresh_rules()

    def refresh_rules(self):
        self.rules_list.clear()

        try:
            options = loadUserOptions()
            rules = options.get("rules", [])
            self.max_emails.set(str(options.get("max_emails", 100)))
        except Exception as error:
            ttk.Label(
                self.rules_list.content,
                text=f"Failed to load rules: {error}",
            ).pack(padx=10, pady=10)
            return

        indexed_rules = sorted(
            enumerate(rules),
            key=lambda item: item[1].get("priority", 100),
        )

        if not indexed_rules:
            ttk.Label(
                self.rules_list.content,
                text="No rules have been configured yet.",
            ).pack(padx=10, pady=20)
            return

        for rule_index, rule in indexed_rules:
            RuleCard(
                self.rules_list.content,
                rule,
                destinations=self.destinations,
                on_save=lambda updated_rule, index=rule_index: self.save_rule(
                    index, updated_rule
                ),
                on_delete=lambda index=rule_index: self.delete_rule(index),
            ).pack(
                fill="x",
                padx=4,
                pady=4,
            )

    def save_max_emails(self):
        try:
            max_emails = int(self.max_emails.get())
            if not 1 <= max_emails <= 10000:
                raise ValueError
        except ValueError:
            self.max_emails_status.config(
                text="Enter a whole number from 1 to 10000.",
                foreground="red",
            )
            return

        options = loadUserOptions()
        options["max_emails"] = max_emails
        saveUserOptions(options)
        self.max_emails.set(str(max_emails))
        self.max_emails_status.config(text="Saved", foreground="green")

    def show_new_rule_editor(self):
        self.rules_list.clear()

        editor_box = ttk.LabelFrame(
            self.rules_list.content,
            text="New rule",
            padding=6,
            bootstyle="primary",
        )
        editor_box.pack(fill="x", padx=4, pady=4)

        RuleEditor(
            editor_box,
            create_rule_template(),
            on_save=self.add_rule,
            on_cancel=self.refresh_rules,
            allow_match_type_changes=True,
            allow_action_type_changes=True,
            destinations=self.destinations,
        ).pack(fill="x")

    def add_rule(self, new_rule):
        options = loadUserOptions()
        options.setdefault("rules", []).append(new_rule)
        saveUserOptions(options)
        self.refresh_rules()

    def save_rule(self, rule_index, updated_rule):
        options = loadUserOptions()
        rules = options.setdefault("rules", [])

        if rule_index >= len(rules):
            raise IndexError("The rule no longer exists.")

        rules[rule_index] = updated_rule
        saveUserOptions(options)
        self.refresh_rules()

    def delete_rule(self, rule_index):
        options = loadUserOptions()
        rules = options.setdefault("rules", [])

        if rule_index >= len(rules):
            raise IndexError("The rule no longer exists.")

        rules.pop(rule_index)
        saveUserOptions(options)
        self.refresh_rules()

    def on_show(self):
        self.preview_result = None
        self.apply_button.config(state="disabled")
        self.latest_records = []
        self._show_records([])
        self._refresh_sift_options()
        self.status.config(text="Ready to sift.")
        self.refresh_destinations()

    def refresh_destinations(self):
        if self.sifting or self.loading_destinations or self.controller.closing:
            return
        self.loading_destinations = True
        self.destinations_button.config(state="disabled")
        self.controller.worker.submit(
            lambda report: self.controller.email_agent.list_destinations(),
            self._destinations_loaded, self._destinations_failed,
        )

    def _destinations_loaded(self, destinations):
        self.loading_destinations = False
        self.destinations = destinations
        self.destinations_button.config(state="normal")
        self.refresh_rules()

    def _destinations_failed(self, error):
        self.loading_destinations = False
        self.destinations_button.config(state="normal")
        self.status.config(text=f"Could not load folders / labels: {error_text(error)}.")

    def _build_results_tab(self):
        ttk.Label(self.results_tab, text="Review each action before applying it. Completed actions are skipped when resuming.",
                  wraplength=700).pack(anchor="w", padx=20, pady=12)
        box = ttk.Frame(self.results_tab)
        box.pack(fill="both", expand=True, padx=20)
        self.results = ttk.Treeview(box, columns=("subject", "rule", "action", "status", "details"), show="headings")
        for column, width in (("subject", 200), ("rule", 130), ("action", 70), ("status", 80), ("details", 240)):
            self.results.heading(column, text=column.title())
            self.results.column(column, width=width, minwidth=60)
        vertical = ttk.Scrollbar(box, orient="vertical", command=self.results.yview)
        horizontal = ttk.Scrollbar(box, orient="horizontal", command=self.results.xview)
        self.results.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.results.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        box.grid_rowconfigure(0, weight=1)
        box.grid_columnconfigure(0, weight=1)
        buttons = ttk.Frame(self.results_tab)
        buttons.pack(fill="x", padx=20, pady=12)
        ttk.Button(buttons, text="Export report", command=self.export_report).pack(side="left")
        ttk.Button(buttons, text="Retry selected uncertain action", command=lambda: self.resolve_action(False)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Mark selected action completed", command=lambda: self.resolve_action(True)).pack(side="left")

    def _show_records(self, records):
        self.latest_records = records
        self.result_rows = {}
        self.results.delete(*self.results.get_children())
        for row in records:
            for index, step in enumerate(row["actions"]):
                details = step.get("error") or json.dumps(step["settings"], ensure_ascii=False)
                item = self.results.insert("", "end", values=(row["subject"], step["rule"], step["action"], step["status"], details))
                self.result_rows[item] = (row["message_id"], index, step["status"])

    def resolve_action(self, completed):
        if self.sifting or not self.preview_result or not self.preview_result.journal:
            return
        selected = self.results.selection()
        allowed = {"pending", "uncertain"} if completed else {"uncertain"}
        if not selected or self.result_rows[selected[0]][2] not in allowed:
            messagebox.showinfo("Select an action", "Preview the interrupted batch, then select an action that needs review.", parent=self)
            return
        message_id, index, _ = self.result_rows[selected[0]]
        if not messagebox.askyesno("Review mailbox first", "Check this message in your mailbox first.\n\n" + (
            "Marking this action completed will skip it on resume. Continue?" if completed else
            "Retrying may repeat a change the server already applied. Continue?"), parent=self):
            return
        try:
            self.preview_result.journal.resolve(message_id, index, completed, batch_id=self.preview_result.batch["batch_id"])
        except Exception as error:
            self.status.config(text=f"Could not update recovery record: {error}")
            return
        self.attempt_go()

    def export_report(self):
        filename = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("JSON", "*.json")])
        if filename:
            try:
                from app.services.journal import write_private_json
                write_private_json(filename, {"messages": self.latest_records})
            except Exception as error:
                messagebox.showerror("Export failed", str(error), parent=self)

    def _refresh_sift_options(self):
        try:
            options = loadUserOptions()
        except Exception:
            return

        saved_mode = options.get("sift_mode", "since_last")
        if saved_mode in {"since_last", "all"}:
            self.sift_mode.set(saved_mode)

        last_sift_at = options.get("last_sift_at")
        if last_sift_at:
            display_time = last_sift_at.replace("T", " ").removesuffix("Z")
            self.last_sift_label.config(text=f"Sift checkpoint: {display_time} UTC")
        else:
            self.last_sift_label.config(text="No previous successful sift recorded")

    def _set_busy(self, busy):
        self.sifting = busy
        self.go_button.config(state="disabled" if busy else "normal")
        self.logout_button.config(state="disabled" if busy else "normal")
        self.cancel_button.config(state="normal" if busy else "disabled")
        if hasattr(self, "apply_button"):
            self.apply_button.config(state="disabled")
        if not busy:
            self.progress.stop()

    def apply_preview(self):
        if self.preview_result is not None:
            self.attempt_go(preview=False)

    def attempt_go(self, preview=True):
        if self.sifting or self.controller.closing:
            return
        try:
            options = loadUserOptions()
        except Exception as error:
            self.status.config(text=f"Could not load rules: {error}")
            return
        mode = self.sift_mode.get()
        prepared = self.preview_result.batch if not preview and self.preview_result else None
        if not preview and prepared is None:
            return
        if preview:
            self.preview_result = None
        client = self.controller.email_agent
        self.cancel_event = Event()
        cancel = self.cancel_event
        self._set_busy(True)
        self.progress.config(mode="indeterminate", maximum=100, value=0)
        self.progress.start()
        self.status.config(text="Refreshing inbox...")
        self.controller.worker.submit(
            lambda report: sift(client, options, mode, cancel, report, preview=preview, prepared=prepared),
            self._sift_finished, self._sift_failed, self._sift_progress,
        )

    def cancel_sift(self):
        if self.sifting:
            self.cancel_event.set()
            self.cancel_button.config(state="disabled")
            self.status.config(text="Stopping after the current message/request finishes...")

    def _sift_progress(self, text, done, total):
        if total:
            self.progress.stop()
            self.progress.config(mode="determinate", maximum=total, value=done)
        if not self.cancel_event.is_set():
            self.status.config(text=f"{text} {done}/{total}" if total else text)

    def _sift_finished(self, result):
        self._set_busy(False)
        if hasattr(self, "_show_records"):
            self._show_records(result.records)
        if result.preview:
            self.preview_result = result
            uncertain = any(step["status"] == "uncertain" for row in result.records for step in row["actions"])
            self.apply_button.config(state="disabled" if uncertain or result.warnings else "normal")
            count = sum(len(row["actions"]) for row in result.records)
            self.status.config(text=f"Preview: {result.examined} emails, {count} actions. " + (
                " ".join(result.warnings) if result.warnings else
                "Review uncertain actions in Results before resuming." if uncertain else "Review Results, then choose Apply preview on Sift."))
            self.progress.stop()
            self.progress.config(mode="determinate", maximum=100, value=100)
            self.notebook.select(self.results_tab)
            return
        self.preview_result = None
        # Explicitly finish even when the inbox was empty and no per-message
        # progress events were emitted. Set this after stopping animation.
        self.progress.config(mode="determinate", maximum=100, value=100)
        try:
            # Merge into current settings so edits made during a run survive.
            if result.journal:
                result.journal.commit(result.batch["batch_id"])
            else:
                options = loadUserOptions()
                options.update(result.settings_update)
                saveUserOptions(options)
        except Exception as error:
            self.status.config(text=f"Emails processed, but checkpoint could not be saved: {error}")
            return
        self.status.config(text=(
            f"Examined {result.examined} emails; modified {result.modified} emails "
            f"with {result.modifications} actions."
        ))
        self._refresh_sift_options()

    def _sift_failed(self, error):
        self._set_busy(False)
        if hasattr(error, "records"):
            self._show_records(error.records)
        detail = "Sift cancelled." if isinstance(error, SiftCancelled) else f"Sift failed: {error_text(error)}."
        self.status.config(text=f"{detail} Completed changes remain; checkpoint was not advanced. Preview again to recover.")

    def logout(self):
        if self.sifting or self.controller.closing:
            return
        client = self.controller.email_agent
        self._set_busy(True)
        self.cancel_button.config(state="disabled")
        self.status.config(text="Signing out...")

        async def disconnect(report):
            client.logout()
            await client.close()

        self.controller.worker.submit(disconnect, self._logged_out, self._logout_failed)

    def _logged_out(self, _result):
        self._set_busy(False)
        self.controller.email_agent = None
        self.destinations = {}
        self.preview_result = None
        self.status.config(text="")
        if not self.controller.closing:
            self.controller.show_page("Login")

    def _logout_failed(self, error):
        self._set_busy(False)
        self.status.config(text=f"Sign out failed: {error}. Try again.")
