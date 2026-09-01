"""Generic editors that preserve common JSON value types."""

import tkinter as tk
from tkinter import ttk


class FieldEditor(ttk.Frame):
    """Edit the existing fields in a dictionary without losing their types."""

    def __init__(self, parent, values):
        super().__init__(parent)
        self._fields = {}

        if not values:
            ttk.Label(self, text="No additional settings").pack(anchor="w")
            return

        for row, (name, value) in enumerate(values.items()):
            ttk.Label(self, text=self._label(name)).grid(
                row=row,
                column=0,
                sticky="nw",
                padx=(0, 10),
                pady=3,
            )

            editor = self._create_editor(value)
            editor["widget"].grid(row=row, column=1, sticky="ew", pady=3)
            self._fields[name] = editor

        self.grid_columnconfigure(1, weight=1)

    def values(self):
        return {
            name: self._read_editor(editor)
            for name, editor in self._fields.items()
        }

    def _create_editor(self, value):
        if isinstance(value, dict):
            widget = FieldEditor(self, value)
            return {"kind": "dict", "widget": widget}

        if isinstance(value, bool):
            variable = tk.StringVar(value="Yes" if value else "No")
            widget = ttk.Combobox(
                self,
                textvariable=variable,
                values=("Yes", "No"),
                state="readonly",
            )
            return {"kind": "bool", "widget": widget, "variable": variable}

        if isinstance(value, list):
            variable = tk.StringVar(value=", ".join(map(str, value)))
            widget = ttk.Entry(self, textvariable=variable)
            return {"kind": "list", "widget": widget, "variable": variable}

        variable = tk.StringVar(value="" if value is None else str(value))
        widget = ttk.Entry(self, textvariable=variable)
        return {
            "kind": "scalar",
            "widget": widget,
            "variable": variable,
            "original": value,
        }

    @staticmethod
    def _read_editor(editor):
        kind = editor["kind"]
        if kind == "dict":
            return editor["widget"].values()

        text = editor["variable"].get().strip()
        if kind == "bool":
            return text == "Yes"
        if kind == "list":
            return [item.strip() for item in text.split(",") if item.strip()]

        original = editor["original"]
        if isinstance(original, int) and not isinstance(original, bool):
            return int(text)
        if isinstance(original, float):
            return float(text)
        if original is None and not text:
            return None
        return text

    @staticmethod
    def _label(name):
        return str(name).replace("_", " ").strip().title() + ":"
