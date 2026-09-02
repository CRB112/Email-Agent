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


class MarkFieldEditor(ttk.Frame):
    """Editor for the related Mark_type and Mark_op action settings."""

    OPERATIONS = {
        "Read": ("Read", "Unread"),
        "Importance": ("Low", "Normal", "High"),
    }

    def __init__(self, parent, values):
        super().__init__(parent)

        mark_type = values.get("Mark_type", "Read")
        if mark_type not in self.OPERATIONS:
            mark_type = "Read"
        mark_op = values.get("Mark_op")
        if mark_op not in self.OPERATIONS[mark_type]:
            mark_op = self.OPERATIONS[mark_type][0]

        self.mark_type = tk.StringVar(value=mark_type)
        self.mark_op = tk.StringVar(value=mark_op)

        ttk.Label(self, text="Mark Type:").grid(
            row=0, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        type_editor = ttk.Combobox(
            self,
            textvariable=self.mark_type,
            values=tuple(self.OPERATIONS),
            state="readonly",
        )
        type_editor.grid(row=0, column=1, sticky="ew", pady=3)
        type_editor.bind("<<ComboboxSelected>>", self._change_mark_type)

        ttk.Label(self, text="Mark Op:").grid(
            row=1, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        self.op_editor = ttk.Combobox(
            self,
            textvariable=self.mark_op,
            values=self.OPERATIONS[mark_type],
            state="readonly",
        )
        self.op_editor.grid(row=1, column=1, sticky="ew", pady=3)
        self.grid_columnconfigure(1, weight=1)

    def _change_mark_type(self, _event):
        operations = self.OPERATIONS[self.mark_type.get()]
        self.op_editor.configure(values=operations)
        self.mark_op.set(operations[0])

    def values(self):
        return {
            "Mark_type": self.mark_type.get(),
            "Mark_op": self.mark_op.get(),
        }
