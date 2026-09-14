"""Main application page and its notebook tabs."""

import tkinter as tk
from threading import Event

import ttkbootstrap as ttk

from app.microsoftGraph.email import logout as logout_user
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
class MainPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.sifting = False
        self.cancel_event = Event()
        self.sift_mode = tk.StringVar(value="since_last")
        self.max_emails = tk.StringVar(value="100")
        self.dark_mode = tk.BooleanVar(value=self._saved_dark_mode())

        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, padx=16, pady=16)

        self.sift_tab = ttk.Frame(self.notebook)
        self.rules_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.sift_tab, text="Sift")
        self.notebook.add(self.rules_tab, text="Rules")
        self.notebook.add(self.settings_tab, text="Settings")

        self._build_logout_button()
        self._build_sift_tab()
        self._build_rules_tab()
        self._build_settings_tab()

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
            text="All available emails again",
            variable=self.sift_mode,
            value="all",
        ).pack(anchor="w")

        self.last_sift_label = ttk.Label(self.sift_tab, text="")
        self.last_sift_label.pack(pady=(8, 0))
        self._refresh_sift_options()

        self.go_button = ttk.Button(
            self.sift_tab,
            text="Go",
            command=self.attempt_go,
            bootstyle="success",
            padding=(34, 10),
        )
        self.go_button.pack(pady=(20, 8))
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
            if max_emails < 1:
                raise ValueError
        except ValueError:
            self.max_emails_status.config(
                text="Enter a positive whole number.",
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
        self._refresh_sift_options()
        self.status.config(text="Ready to sift.")

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
        if not busy:
            self.progress.stop()

    def attempt_go(self):
        if self.sifting or self.controller.closing:
            return
        try:
            options = loadUserOptions()
        except Exception as error:
            self.status.config(text=f"Could not load rules: {error}")
            return
        mode = self.sift_mode.get()
        client = self.controller.graph_client
        self.cancel_event = Event()
        cancel = self.cancel_event
        self._set_busy(True)
        self.progress.config(mode="indeterminate", maximum=100, value=0)
        self.progress.start()
        self.status.config(text="Refreshing inbox...")
        self.controller.worker.submit(
            lambda report: sift(client, options, mode, cancel, report),
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
        # Explicitly finish even when the inbox was empty and no per-message
        # progress events were emitted. Set this after stopping animation.
        self.progress.config(mode="determinate", maximum=100, value=100)
        try:
            # Merge into current settings so edits made during a run survive.
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
        detail = "Sift cancelled." if isinstance(error, SiftCancelled) else f"Sift failed: {error}."
        self.status.config(text=f"{detail} Completed changes remain; checkpoint was not advanced.")

    def logout(self):
        if self.sifting or self.controller.closing:
            return
        logout_user()
        self.controller.graph_client = None
        self.status.config(text="")
        self.controller.show_page("Login")
