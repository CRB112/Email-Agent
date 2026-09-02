"""Microsoft login page."""

import ttkbootstrap as ttk

from app.microsoftGraph.email import authenticate


class LoginPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        card = ttk.Frame(self, padding=40)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            card,
            text="Email Sifting Agent",
            font=("Mouldy Cheese", 30),
            bootstyle="primary",
        ).pack(pady=(0, 10))

        ttk.Label(
            card,
            text="Connect your Microsoft account to organize your inbox.",
            font=("TkDefaultFont", 11),
            bootstyle="secondary",
        ).pack(pady=(0, 28))

        ttk.Button(
            card,
            text="Log in with Microsoft",
            command=self.login,
            bootstyle="primary",
            padding=(24, 10),
        ).pack(fill="x")

        self.status = ttk.Label(
            card,
            text="",
            wraplength=420,
            justify="center",
            bootstyle="secondary",
        )
        self.status.pack(pady=(18, 0))

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
