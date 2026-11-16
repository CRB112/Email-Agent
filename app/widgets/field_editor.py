"""Generic editors that preserve common JSON value types."""

import tkinter as tk
import ttkbootstrap as ttk

from app.rules.definitions import FIELD_CHOICES


class FieldEditor(ttk.Frame):
    """Edit the existing fields in a dictionary without losing their types."""

    def __init__(self, parent, values, destinations=None):
        super().__init__(parent)
        self._fields = {}
        self.destinations = destinations or {}

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

            editor = self._create_editor(name, value)
            editor["widget"].grid(row=row, column=1, sticky="ew", pady=3)
            self._fields[name] = editor

        self.grid_columnconfigure(1, weight=1)
        if "Folder" in self._fields and not self.destinations:
            ttk.Label(
                self, text="No folders or labels loaded. Use Refresh folders / labels on the Rules tab.",
                wraplength=320, justify="left", bootstyle="warning",
            ).grid(row=len(values), column=0, columnspan=2, sticky="w", pady=(4, 0))

    def values(self):
        return {
            name: self._read_editor(editor)
            for name, editor in self._fields.items()
        }

    def _create_editor(self, name, value):
        if name == "Folder":
            display = next((label for label, identifier in self.destinations.items() if identifier == value), value)
            variable = tk.StringVar(value=display)
            widget = ttk.Combobox(self, textvariable=variable, values=tuple(self.destinations), state="readonly")
            return {"kind": "destination", "widget": widget, "variable": variable,
                    "destinations": self.destinations}
        if isinstance(value, dict):
            widget = FieldEditor(self, value)
            return {"kind": "dict", "widget": widget}

        if name in FIELD_CHOICES:
            variable = tk.StringVar(value=str(value))
            widget = ttk.Combobox(
                self,
                textvariable=variable,
                values=FIELD_CHOICES[name],
                state="readonly",
            )
            return {"kind": "choice", "widget": widget, "variable": variable}

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
        if kind == "destination":
            return editor["destinations"].get(text, text)
        if kind == "bool":
            return text == "Yes"
        if kind == "choice":
            return text
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
        if name == "Folder":
            return "Folder / label:"
        return str(name).replace("_", " ").strip().title() + ":"


class MarkFieldEditor(ttk.Frame):
    """Editor for the related Mark_type and Mark_op action settings."""

    OPERATIONS = {
        "Read": ("Read", "Unread"),
        "Importance": ("Low", "Normal", "High"),
    }
    TYPE_LABELS = {"Read": "Read status", "Importance": "Importance"}

    def __init__(self, parent, values):
        super().__init__(parent)

        mark_type = values.get("Mark_type", "Read")
        if mark_type not in self.OPERATIONS:
            mark_type = "Read"
        mark_op = values.get("Mark_op")
        if mark_op not in self.OPERATIONS[mark_type]:
            mark_op = "Read" if mark_type == "Read" else "Normal"

        self.mark_type = tk.StringVar(value=mark_type)
        self.mark_type_display = tk.StringVar(value=self.TYPE_LABELS[mark_type])
        self.mark_op = tk.StringVar(value=mark_op)

        ttk.Label(self, text="Change:").grid(
            row=0, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        self.type_editor = ttk.Combobox(
            self,
            textvariable=self.mark_type_display,
            values=tuple(self.TYPE_LABELS.values()),
            state="readonly",
        )
        self.type_editor.grid(row=0, column=1, sticky="ew", pady=3)
        self.type_editor.bind("<<ComboboxSelected>>", self._change_mark_type)

        ttk.Label(self, text="Set to:").grid(
            row=1, column=0, sticky="nw", padx=(0, 10), pady=3
        )
        self.op_editor = ttk.Combobox(
            self,
            textvariable=self.mark_op,
            values=self.OPERATIONS[mark_type],
            state="readonly",
        )
        self.op_editor.grid(row=1, column=1, sticky="ew", pady=3)
        self.op_editor.bind("<<ComboboxSelected>>", self._update_help)
        self.help_label = ttk.Label(self, wraplength=320, justify="left", bootstyle="secondary")
        self.help_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.help_label.bind("<Configure>", lambda event: event.widget.configure(
            wraplength=max(80, event.width)))
        self._update_help()
        self.grid_columnconfigure(1, weight=1)

    def _change_mark_type(self, _event):
        self.mark_type.set(next(kind for kind, label in self.TYPE_LABELS.items()
                                if label == self.mark_type_display.get()))
        operations = self.OPERATIONS[self.mark_type.get()]
        self.op_editor.configure(values=operations)
        self.mark_op.set("Read" if self.mark_type.get() == "Read" else "Normal")
        self._update_help()

    def _update_help(self, _event=None):
        if self.mark_type.get() == "Read":
            text = f"Matching emails will be marked as {self.mark_op.get().lower()}."
        else:
            text = (f"Set matching emails to {self.mark_op.get().lower()} importance. "
                    "In Gmail, High sets Important; Normal and Low clear Important.")
        self.help_label.configure(text=text)

    def values(self):
        return {
            "Mark_type": self.mark_type.get(),
            "Mark_op": self.mark_op.get(),
        }
