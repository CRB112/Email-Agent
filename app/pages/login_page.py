"""Microsoft login page."""

import tkinter as tk
from tkinter import ttk

from app.microsoftGraph.email import authenticate


class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        title = tk.Label(self, text="Please Log In", font=("Mouldy Cheese", 24))
        title.pack(pady=(20, 30))

        ttk.Button(self, text="Log In", command=self.login).pack(pady=60)

        self.status = tk.Label(self, text="")
        self.status.pack()

    def on_show(self):
        self.status.config(text="")

    def login(self):
        self.status.config(text="Connecting to Outlook...")
        self.update_idletasks()

        try:
            self.controller.graph_client = authenticate()
        except Exception as error:
            self.status.config(text=f"Login failed: {error}")
            return

        self.controller.show_page("Main")
