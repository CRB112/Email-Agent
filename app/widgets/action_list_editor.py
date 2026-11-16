import copy
import ttkbootstrap as ttk

from app.rules.definitions import ACTION_DEFINITIONS
from app.widgets.field_editor import FieldEditor, MarkFieldEditor


class ActionListEditor(ttk.Frame):
    DESCRIPTIONS = {
        "Mark": "Change read status or importance without moving the email.",
        "Move": "Choose a folder or Gmail label for matching emails.",
        "Delete": "Delete matching emails after the other actions. Gmail moves them to Trash.",
    }

    def __init__(self, parent, actions, allow_changes=True, destinations=None):
        super().__init__(parent)
        self.actions = copy.deepcopy(actions)
        self.allow_changes = allow_changes
        self.destinations = destinations
        self._editors = {}
        self.add_buttons = {}
        self.remove_buttons = {}

        if allow_changes:
            controls = ttk.Frame(self)
            controls.pack(fill="x", pady=(0, 8))
            for column, action in enumerate(("Mark", "Move", "Delete")):
                button = ttk.Button(
                    controls, text=f"Add {action}",
                    command=lambda name=action: self.add_action(name),
                    bootstyle="danger outline" if action == "Delete" else "primary outline",
                )
                button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
                controls.grid_columnconfigure(column, weight=1, uniform="actions")
                self.add_buttons[action] = button

        self.action_rows = ttk.Frame(self)
        self.action_rows.pack(fill="x")

        self._render()

    def values(self):
        return {
            action: editor.values()
            for action, editor in self._editors.items()
        }

    def add_action(self, action):
        self._capture_values()
        if action in self.actions:
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
        self.remove_buttons = {}

        for action, settings in self.actions.items():
            action_box = ttk.LabelFrame(
                self.action_rows,
                text=action,
                padding=8,
            )
            action_box.pack(fill="x", pady=(0, 6))
            action_box.grid_columnconfigure(0, weight=1)

            description = ttk.Label(
                action_box, text=self.DESCRIPTIONS[action],
                wraplength=300, justify="left", bootstyle="secondary",
            )
            description.grid(row=0, column=0, sticky="ew", pady=(0, 6))
            description.bind("<Configure>", lambda event: event.widget.configure(
                wraplength=max(80, event.width)))

            editor_class = MarkFieldEditor if action == "Mark" else FieldEditor
            kwargs = {"destinations": self.destinations} if action == "Move" else {}
            editor = editor_class(action_box, settings, **kwargs)
            editor.grid(row=1, column=0, columnspan=2, sticky="ew")
            self._editors[action] = editor

            if self.allow_changes:
                button = ttk.Button(
                    action_box,
                    text=f"Remove {action}",
                    command=lambda name=action: self.remove_action(name),
                    bootstyle="danger outline",
                )
                button.grid(row=0, column=1, sticky="ne", padx=(8, 0))
                self.remove_buttons[action] = button

        if not self.actions:
            ttk.Label(
                self.action_rows,
                text="No actions selected. Add an action above to configure what happens to matching emails.",
                wraplength=350, justify="left",
                bootstyle="secondary",
            ).pack(anchor="w", pady=4)

        if self.allow_changes:
            for action, button in self.add_buttons.items():
                button.configure(state="disabled" if action in self.actions else "normal")
