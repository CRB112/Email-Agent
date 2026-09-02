import asyncio
from pathlib import Path

import ttkbootstrap as ttk

from app.microsoftGraph.email import authenticate
from app.pages.pages import PAGES_LIST
from app.parser.parser import loadUserOptions

AUTH_RECORD_FILE = Path.home() / ".email-sifting-auth.json"


def get_saved_theme():
    try:
        dark_mode = loadUserOptions().get("dark_mode", False)
    except Exception:
        dark_mode = False
    return "darkly" if dark_mode else "flatly"


class MainWindow(ttk.Window):
    def __init__(self):
        super().__init__(
            title="Email Sifting Agent",
            theme=get_saved_theme(),
            size=(900, 640),
            minsize=(760, 520),
        )

        self.graph_client = None
        self.async_loop = asyncio.new_event_loop()
        self.protocol("WM_DELETE_WINDOW", self.close)

        container = ttk.Frame(self)
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

    def run_async(self, operation):
        """Run Graph operations on the application's persistent event loop."""
        return self.async_loop.run_until_complete(operation)

    def close(self):
        if not self.async_loop.is_closed():
            self.async_loop.close()
        self.destroy()


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
