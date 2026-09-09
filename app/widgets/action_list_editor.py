import copy
import tkinter as tk

import ttkbootstrap as ttk

from app.rules.definitions import ACTION_DEFINITIONS
from app.widgets.field_editor import FieldEditor, MarkFieldEditor


class ActionListEditor(ttk.Frame):
    def __init__(self, parent, actions, allow_changes=True):
        super().__init__(parent)
        self.actions = copy.deepcopy(actions)
        self.allow_changes = allow_changes
        self.action_to_add = tk.StringVar()
        self._editors = {}

        self.action_rows = ttk.Frame(self)
        self.action_rows.pack(fill="x")

        if allow_changes:
            controls = ttk.Frame(self)
            controls.pack(fill="x", pady=(6, 0))
            self.action_selector = ttk.Combobox(
                controls,
                textvariable=self.action_to_add,
                state="readonly",
                width=14,
            )
            self.action_selector.pack(side="left", fill="x", expand=True)
            ttk.Button(
                controls,
                text="Add action",
                command=self.add_action,
                bootstyle="primary outline",
            ).pack(side="left", padx=(6, 0))

        self._render()

    def values(self):
        return {
            action: editor.values()
            for action, editor in self._editors.items()
        }

    def add_action(self):
        self._capture_values()
        action = self.action_to_add.get()
        if not action or action in self.actions:
            return
        self.actions[action] = copy.deepcopy(ACTION_DEFINITIONS[action])
        self._render()

    def remove_action(self, action):
        self._capture_values()
        self.actions.pop(action, None)
        self._render()

    def _capture_values(self):
        if self._editors:
            self.actions = self.values()

    def _render(self):
        for child in self.action_rows.winfo_children():
            child.destroy()
        self._editors = {}

        for action, settings in self.actions.items():
            action_box = ttk.LabelFrame(
                self.action_rows,
                text=action,
                padding=8,
            )
            action_box.pack(fill="x", pady=(0, 6))

            editor_class = MarkFieldEditor if action == "Mark" else FieldEditor
            editor = editor_class(action_box, settings)
            editor.pack(side="left", fill="x", expand=True)
            self._editors[action] = editor

            if self.allow_changes:
                ttk.Button(
                    action_box,
                    text="Remove",
                    command=lambda name=action: self.remove_action(name),
                    bootstyle="danger outline",
                ).pack(side="right", padx=(8, 0), anchor="n")

        if not self.actions:
            ttk.Label(
                self.action_rows,
                text="No actions added yet.",
                bootstyle="secondary",
            ).pack(anchor="w", pady=4)

        if self.allow_changes:
            available = [
                action for action in ACTION_DEFINITIONS
                if action not in self.actions
            ]
            self.action_selector.configure(
                values=available,
                state="readonly" if available else "disabled",
            )
            self.action_to_add.set(available[0] if available else "")
