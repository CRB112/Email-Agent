"""Collapsible rule summary widget."""

import re
import tkinter as tk
from tkinter import messagebox, ttk

from app.widgets.rule_editor import RuleEditor


class RuleCard(ttk.Frame):
    def __init__(self, parent, rule, on_save=None, on_delete=None):
        super().__init__(parent, relief="solid", borderwidth=1, padding=6)
        self.expanded = False
        self.rule = rule
        self.on_save = on_save
        self.on_delete = on_delete
        self.editor = None
        self.header_text = tk.StringVar()

        ttk.Button(
            self, textvariable=self.header_text, command=self.toggle
        ).pack(fill="x")

        self.details = ttk.Frame(self, padding=(10, 8, 10, 4))
        self._build_details()
        self._update_header()

    def _build_details(self):
        values = (
            ("Match", self._format_match_type(self.rule.get("type"))),
            ("Conditions", self._format_settings(self.rule.get("settings", {}))),
            ("Actions", self._format_actions(self.rule.get("modify", {}))),
            ("Priority", self.rule.get("priority", 100)),
        )

        for row, (label, value) in enumerate(values):
            ttk.Label(
                self.details,
                text=f"{label}:",
                font=("TkDefaultFont", 9, "bold"),
            ).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=3)
            ttk.Label(
                self.details,
                text=str(value),
                justify="left",
                wraplength=360,
            ).grid(row=row, column=1, sticky="nw", pady=3)

        self.details.grid_columnconfigure(1, weight=1)

        actions = ttk.Frame(self.details)
        actions.grid(
            row=len(values),
            column=0,
            columnspan=2,
            sticky="e",
            pady=(8, 0),
        )

        if self.on_delete is not None:
            ttk.Button(
                actions,
                text="Delete",
                command=self.confirm_delete,
            ).pack(side="left", padx=(0, 6))

        if self.on_save is not None:
            ttk.Button(actions, text="Edit", command=self.show_editor).pack(
                side="left"
            )

    def show_editor(self):
        if self.editor is not None:
            return

        self.editor = RuleEditor(
            self,
            self.rule,
            on_save=self.on_save,
            on_cancel=self.hide_editor,
            allow_match_type_changes=True,
        )
        self.editor.pack(fill="x")

    def hide_editor(self):
        if self.editor is not None:
            self.editor.destroy()
            self.editor = None

    def confirm_delete(self):
        rule_name = self.rule.get("name", "this rule")
        confirmed = messagebox.askyesno(
            "Delete rule",
            f'Delete "{rule_name}"?',
            parent=self,
        )
        if confirmed:
            self.on_delete()

    def toggle(self):
        self.expanded = not self.expanded
        if self.expanded:
            self.details.pack(fill="x")
        else:
            self.details.pack_forget()
        self._update_header()

    def _update_header(self):
        arrow = "▼" if self.expanded else "▶"
        name = self.rule.get("name", "Unnamed rule")
        self.header_text.set(f"{arrow}  {name}")

    @staticmethod
    def _readable_name(value):
        if not value:
            return "Not specified"
        value = str(value).replace("_", " ").strip()
        value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
        return value.title()

    @classmethod
    def _format_value(cls, value):
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if value is None:
            return "Not specified"
        if isinstance(value, list):
            return ", ".join(cls._format_value(item) for item in value) or "None"
        if isinstance(value, dict):
            return cls._format_settings(value)
        return str(value)

    @classmethod
    def _format_settings(cls, settings):
        if not settings:
            return "None"
        return "\n".join(
            f"{cls._readable_name(name)}: {cls._format_value(value)}"
            for name, value in settings.items()
        )

    @classmethod
    def _format_match_type(cls, match_type):
        if not match_type:
            return "Not specified"
        return cls._readable_name(str(match_type).removeprefix("match_"))

    @classmethod
    def _format_actions(cls, actions):
        if not actions:
            return "None"

        formatted = []
        for action, settings in actions.items():
            action_name = cls._readable_name(action)
            if settings:
                details = cls._format_settings(settings).replace("\n", "; ")
                formatted.append(f"{action_name} — {details}")
            else:
                formatted.append(action_name)
        return "\n".join(formatted)
