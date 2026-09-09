"""A reusable vertically scrollable Tkinter frame."""

import tkinter as tk
import ttkbootstrap as ttk


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            background=ttk.Style().colors.bg,
        )
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.content = ttk.Frame(self.canvas)

        self._canvas_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_content)

        # Wheel events belong to whichever child widget is under the pointer,
        # not necessarily to the Canvas. Listen application-wide and handle
        # only events originating inside this scrollable frame.
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def sync_theme(self):
        """Match the classic Canvas background to the active ttk theme."""
        self.canvas.configure(background=ttk.Style().colors.bg)

    def _update_scroll_region(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event):
        self.canvas.itemconfigure(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if not self._event_is_inside(event.widget):
            return None

        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None
            direction = -1 if delta > 0 else 1

        self.canvas.yview_scroll(direction, "units")
        return "break"

    def _event_is_inside(self, widget):
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False
