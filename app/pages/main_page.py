"""Main application page and its notebook tabs."""

import tkinter as tk
from tkinter import ttk

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
class MainPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.emails = []
        self.emails_loaded = False

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

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
        logout_button = tk.Button(
            self,
            text="Log out",
            command=self.logout,
            width=8,
            pady=0,
        )
        logout_button.place(relx=1.0, anchor="ne")

    def _build_sift_tab(self):
        tk.Label(
            self.sift_tab,
            text="Home Page",
            font=("Mouldy Cheese", 24),
        ).pack(pady=(70, 30))

        ttk.Button(
            self.sift_tab,
            text="Go",
            command=self.attempt_go,
        ).pack(pady=60)

        self.status = tk.Label(
            self.sift_tab,
            text="",
            justify="center",
            wraplength=540,
        )
        self.status.pack()

    def _build_rules_tab(self):
        heading = ttk.Frame(self.rules_tab)
        heading.pack(fill="x", padx=30, pady=(55, 15))

        tk.Label(
            heading,
            text="Rules",
            font=("Mouldy Cheese", 24),
        ).pack(side="left")

        ttk.Button(
            heading,
            text="Add rule",
            command=self.show_new_rule_editor,
        ).pack(side="right")

        rules_box = ttk.LabelFrame(
            self.rules_tab,
            text="Configured rules",
            padding=8,
        )
        rules_box.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        self.rules_list = ScrollableFrame(rules_box)
        self.rules_list.pack(fill="both", expand=True)

    def _build_settings_tab(self):
        tk.Label(
            self.settings_tab,
            text="Settings",
            font=("Mouldy Cheese", 24),
        ).pack(pady=(70, 20))

        ttk.Label(
            self.settings_tab,
            text="Application settings will go here.",
        ).pack()

    def _on_tab_changed(self, _event):
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        if selected_tab == "Rules":
            self.refresh_rules()

    def refresh_rules(self):
        self.rules_list.clear()

        try:
            options = loadUserOptions()
            rules = options.get("rules", [])
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

    def show_new_rule_editor(self):
        self.rules_list.clear()

        editor_box = ttk.LabelFrame(
            self.rules_list.content,
            text="New rule",
            padding=6,
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

    def load_emails(self):
        self.emails = self.controller.run_async(
            getEmails(self.controller.graph_client)
        )

    def attempt_go(self):
        self.status.config(text="Refreshing inbox...")
        self.update_idletasks()

        try:
            # A previous sift may have deleted or moved messages. Always use
            # fresh Graph message objects and IDs for the next run.
            self.load_emails()
            self.status.config(text="Sifting through emails...")
            self.update_idletasks()

            num_emails, num_modifications = self.controller.run_async(
                parseEmailsWithJson(self.emails, self.controller.graph_client)
            )
        except Exception as error:
            self.status.config(text=f"Failed to sift emails: {error}")
            return

        self.status.config(
            text="Successfully sifted emails! "
            f"Processed {num_emails} emails and made "
            f"{num_modifications} modifications."
        )

    def logout(self):
        logout_user()
        self.controller.graph_client = None
        self.emails = []
        self.emails_loaded = False
        self.status.config(text="")
        self.controller.show_page("Login")
