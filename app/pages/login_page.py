"""Mailbox provider login page."""

import ttkbootstrap as ttk

from app.agents.microsoft import MicrosoftGraphAgent
from app.agents.gmail import GmailAgent
from app.parser.parser import loadUserOptions, saveUserOptions

authenticate = MicrosoftGraphAgent.authenticate


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
            text="Connect your email account.",
            font=("TkDefaultFont", 11),
            bootstyle="secondary",
        ).pack(pady=(0, 28))

        self.login_button = ttk.Button(
            card,
            text="Log in with Microsoft",
            command=self.login,
            bootstyle="primary",
            padding=(24, 10),
        )
        self.login_button.pack(fill="x")

        self.gmail_button = ttk.Button(
            card, text="Log in with Gmail", command=self.login_gmail,
            bootstyle="secondary", padding=(24, 10),
        )
        self.gmail_button.pack(fill="x", pady=(10, 0))

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
        if self.controller.closing or self.login_button.instate(["disabled"]):
            return
        self.login_button.config(state="disabled")
        if hasattr(self, "gmail_button"):
            self.gmail_button.config(state="disabled")
        self.provider = "microsoft"
        self.status.config(text="Connecting to Outlook...")
        self.controller.worker.submit(
            lambda report: authenticate(), self._logged_in, self._login_failed,
        )

    def login_gmail(self):
        if self.controller.closing or self.login_button.instate(["disabled"]):
            return
        self.provider = "gmail"
        self.login_button.config(state="disabled")
        self.gmail_button.config(state="disabled")
        self.status.config(text="Connecting to Gmail...")
        self.controller.worker.submit(
            lambda report: GmailAgent.authenticate(), self._logged_in, self._login_failed,
        )

    def _logged_in(self, client):
        try:
            options = loadUserOptions()
            if not client.mailbox_key or options.get("mailbox_key") != client.mailbox_key:
                options.pop("last_sift_at", None)
                options.pop("last_sift_ids", None)
            options["mailbox_key"] = client.mailbox_key
            options["provider"] = self.provider
            saveUserOptions(options)
        except Exception as error:
            client.logout()
            self._login_failed(error)
            return
        self.login_button.config(state="normal")
        self.gmail_button.config(state="normal")
        self.controller.email_agent = client
        self.controller.show_page("Main")

    def _login_failed(self, error):
        self.login_button.config(state="normal")
        self.gmail_button.config(state="normal")
        self.status.config(text=f"Login failed: {error}")
