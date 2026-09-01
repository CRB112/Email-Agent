import asyncio
import tkinter as tk
from tkinter import ttk
from app.microsoftGraph.email import authenticate, getEmails
from app.parser.parser import parseEmailsWithJson



class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        self.controller = controller

        #TITLE
        title = tk.Label(
            self,
            text="Please Log In",
            font=("Mouldy Cheese", 24),
        )
        title.pack(pady=(20, 30))

        #LOGIN BUTTON
        loginBTN = ttk.Button(
            self, 
            text="Log In",
            command=self.login
        )
        loginBTN.pack(pady=(60))

        self.status = tk.Label(self, text="")
        self.status.pack()

    def login(self):
        self.status.config(text="Connecting to outlook...")
        self.update_idletasks()

        try:
            self.controller.graph_client = authenticate()
        except Exception as error:
            self.status.config(text=f"Login Failed: {error}")
            return

        self.status.config(text="Login success")
        self.controller.show_page("Main")


class MainPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        self.controller = controller
        self.emails = []
        self.emails_loaded = False

        title = tk.Label(
            self,
            text="Home Page",
            font=("Mouldy Cheese", 24),
        )
        title.pack(pady=(70, 30))

        goBTN = ttk.Button(
            self,
            text="Go",
            command = self.attemptGo,
        )
        goBTN.pack(pady=(60))

        self.status = tk.Label(self, text="")
        self.status.pack()

    def on_show(self):
        if self.emails_loaded:
            return

        self.status.config(text="Loading emails...")
        self.update_idletasks()

        try:
            self.emails = asyncio.run(
                getEmails(self.controller.graph_client)
            )
        except Exception as error:
            self.status.config(text=f"Failed to load emails: {error}")
            return

        self.emails_loaded = True
        self.status.config(text=f"Loaded {len(self.emails)} emails")

    def attemptGo(self):
        self.status.config(text=f"Sifting through emails...")
        try:
            asyncio.run(parseEmailsWithJson(self.emails, self.controller.graph_client))
        except Exception as error:
            self.status.config(text=f"Failed to sift emails: {error}")
            return
        self.status.config(text=f"Succesfully sifted emails!")

PAGES_LIST = {
    "Login": LoginPage,
    "Main": MainPage,
}
