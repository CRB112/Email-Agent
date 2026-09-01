import tkinter as tk
from pathlib import Path
from app.microsoftGraph.email import authenticate
from app.pages.pages import PAGES_LIST

AUTH_RECORD_FILE = Path.home() / ".email-sifting-auth.json"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Email Sifting Agent")
        self.geometry("600x400")
        self.graph_client = None

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {}

        for page_name, page_class in PAGES_LIST.items():
            page = page_class(container, self)
            self.pages[page_name] = page

            page.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

        if AUTH_RECORD_FILE.exists():
            self.graph_client = authenticate()
            self.show_page("Main")
        else:
            self.show_page("Login")

    def show_page(self, page_name):
        page = self.pages[page_name]

        if hasattr(page, "on_show"):
            page.on_show()

        page.tkraise()


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
