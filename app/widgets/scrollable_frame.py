"""A reusable vertically scrollable Tkinter frame."""

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0)
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
        self.canvas.bind("<Button-4>", self._scroll_up)
        self.canvas.bind("<Button-5>", self._scroll_down)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _update_scroll_region(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event):
        self.canvas.itemconfigure(self._canvas_window, width=event.width)

    def _scroll_up(self, _event):
        self.canvas.yview_scroll(-1, "units")

    def _scroll_down(self, _event):
        self.canvas.yview_scroll(1, "units")
