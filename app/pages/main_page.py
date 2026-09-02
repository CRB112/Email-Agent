"""Main application page and its notebook tabs."""

import tkinter as tk
from datetime import datetime, timezone

import ttkbootstrap as ttk

from app.microsoftGraph.email import getEmails, logout as logout_user
from app.parser.parser import (
    loadUserOptions,
    parseEmailsWithJson,
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
        self.emails = []
        self.emails_loaded = False
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
        logout_button = ttk.Button(
            self,
            text="Log out",
            command=self.logout,
            bootstyle="danger outline",
            padding=(10, 2),
        )
        logout_button.place(relx=1.0, x=-26, y=19, anchor="ne")

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

        ttk.Button(
            self.sift_tab,
            text="Go",
            command=self.attempt_go,
            bootstyle="success",
            padding=(34, 10),
        ).pack(pady=30)

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
        if self.emails_loaded:
            return

        self.status.config(text="Loading emails...")
        self.update_idletasks()

        try:
            self.load_emails()
        except Exception as error:
            self.status.config(text=f"Failed to load emails: {error}")
            return

        self.emails_loaded = True
        self.status.config(text=f"Loaded {len(self.emails)} emails")

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
            self.last_sift_label.config(text=f"Last successful sift: {display_time} UTC")
        else:
            self.last_sift_label.config(text="No previous successful sift recorded")

    def load_emails(self, received_after=None):
        options = loadUserOptions()
        max_emails = options.get("max_emails", 100)
        self.emails = self.controller.run_async(
            getEmails(
                self.controller.graph_client,
                received_after,
                max_emails,
            )
        )

    def attempt_go(self):
        self.status.config(text="Refreshing inbox...")
        self.update_idletasks()

        try:
            options = loadUserOptions()
            mode = self.sift_mode.get()
            received_after = (
                options.get("last_sift_at") if mode == "since_last" else None
            )
            checkpoint = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            self.load_emails(received_after)
            self.status.config(text="Sifting through emails...")
            self.update_idletasks()

            num_emails, num_modifications = self.controller.run_async(
                parseEmailsWithJson(self.emails, self.controller.graph_client)
            )

            options["sift_mode"] = mode
            options["last_sift_at"] = checkpoint
            saveUserOptions(options)
        except Exception as error:
            self.status.config(text=f"Failed to sift emails: {error}")
            return

        self.status.config(
            text="Successfully sifted emails! "
            f"Processed {num_emails} emails and made "
            f"{num_modifications} modifications."
        )
        self._refresh_sift_options()

    def logout(self):
        logout_user()
        self.controller.graph_client = None
        self.emails = []
        self.emails_loaded = False
        self.status.config(text="")
        self.controller.show_page("Login")
