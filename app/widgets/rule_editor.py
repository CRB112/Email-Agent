"""Inline editor for an existing email rule."""

import copy
import tkinter as tk
from tkinter import ttk

from app.rules.definitions import (
    ACTION_DEFINITIONS,
    MATCH_DEFINITIONS,
    MATCH_TYPES_BY_LABEL,
    match_type_label,
)
from app.widgets.field_editor import FieldEditor, MarkFieldEditor


class RuleEditor(ttk.Frame):
    def __init__(
        self,
        parent,
        rule,
        on_save,
        on_cancel,
        allow_match_type_changes=False,
        allow_action_type_changes=False,
    ):
        super().__init__(parent, padding=(10, 8))
        self.rule = copy.deepcopy(rule)
        self.on_save = on_save
        self.allow_action_type_changes = allow_action_type_changes

        self.name = tk.StringVar(value=self.rule.get("name", ""))
        self.priority = tk.StringVar(value=str(self.rule.get("priority", 100)))
        self.match_type = tk.StringVar(value=self.rule.get("type", ""))
        self.match_type_display = tk.StringVar(
            value=match_type_label(self.match_type.get())
        )
        self.action_type = tk.StringVar(
            value=next(iter(self.rule.get("modify", {})), "")
        )

        self._add_entry("Name", self.name, 0)

        ttk.Label(self, text="Match type:").grid(
            row=1, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        if allow_match_type_changes:
            match_selector = ttk.Combobox(
                self,
                textvariable=self.match_type_display,
                values=tuple(MATCH_TYPES_BY_LABEL),
                state="readonly",
            )
            match_selector.grid(row=1, column=1, sticky="ew", pady=3)
            match_selector.bind("<<ComboboxSelected>>", self._change_match_type)
        else:
            ttk.Label(
                self,
                text=self.match_type_display.get() or "Not specified",
            ).grid(
                row=1, column=1, sticky="nw", pady=3
            )

        self._add_entry("Priority", self.priority, 2)

        ttk.Label(self, text="Conditions:").grid(
            row=3, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        self.condition_container = ttk.Frame(self)
        self.condition_container.grid(row=3, column=1, sticky="ew", pady=3)
        self._build_condition_editor()

        ttk.Label(self, text="Action:").grid(
            row=4, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        self.action_container = ttk.Frame(self)
        self.action_container.grid(row=4, column=1, sticky="ew", pady=3)

        if allow_action_type_changes:
            action_selector = ttk.Combobox(
                self.action_container,
                textvariable=self.action_type,
                values=tuple(ACTION_DEFINITIONS),
                state="readonly",
            )
            action_selector.pack(fill="x", pady=(0, 4))
            action_selector.bind("<<ComboboxSelected>>", self._change_action_type)

        self.action_fields = ttk.Frame(self.action_container)
        self.action_fields.pack(fill="x")
        self._build_action_editor()

        self.error = ttk.Label(self, text="", foreground="red")
        self.error.grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=on_cancel).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left")

        self.grid_columnconfigure(1, weight=1)

    def _build_condition_editor(self):
        for child in self.condition_container.winfo_children():
            child.destroy()
        self.condition_editor = FieldEditor(
            self.condition_container,
            self.rule.get("settings", {}),
        )
        self.condition_editor.pack(fill="x")

    def _build_action_editor(self):
        for child in self.action_fields.winfo_children():
            child.destroy()
        action = self._action_name()
        settings = self.rule.get("modify", {}).get(action, {})
        editor_class = (
            MarkFieldEditor if action == "Mark" else FieldEditor
        )
        self.action_editor = editor_class(self.action_fields, settings)
        self.action_editor.pack(fill="x")

    def _action_name(self):
        if self.allow_action_type_changes:
            return self.action_type.get()
        return next(iter(self.rule.get("modify", {})), "")

    def _change_match_type(self, _event):
        match_type = MATCH_TYPES_BY_LABEL[self.match_type_display.get()]
        self.match_type.set(match_type)
        self.rule["type"] = match_type
        self.rule["settings"] = copy.deepcopy(MATCH_DEFINITIONS[match_type])
        self._build_condition_editor()

    def _change_action_type(self, _event):
        action = self.action_type.get()
        self.rule["modify"] = {
            action: copy.deepcopy(ACTION_DEFINITIONS[action])
        }
        self._build_action_editor()

    def _add_entry(self, label, variable, row):
        ttk.Label(self, text=f"{label}:").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=3
        )
        ttk.Entry(self, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=3
        )

    def save(self):
        name = self.name.get().strip()
        if not name:
            self.error.config(text="A rule name is required.")
            return

        try:
            priority = int(self.priority.get())
            conditions = self.condition_editor.values()
            action_values = self.action_editor.values()
        except ValueError:
            self.error.config(text="Priority and numeric settings must be numbers.")
            return

        self.rule["name"] = name
        self.rule["priority"] = priority
        self.rule["type"] = self.match_type.get()
        self.rule["settings"] = conditions
        action = self._action_name()
        self.rule["modify"] = {action: action_values}

        try:
            self.on_save(self.rule)
        except Exception as error:
            self.error.config(text=f"Could not save rule: {error}")
