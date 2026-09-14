from pathlib import Path

import ttkbootstrap as ttk

from app.services.worker import BackgroundWorker
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
        self.worker = BackgroundWorker()
        self.closing = False
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

        self.show_page("Login")
        self.after(50, self._poll_worker)
        if AUTH_RECORD_FILE.exists():
            self.after(0, self.pages["Login"].login)

    def _poll_worker(self):
        if self.closing:
            if not self.worker.thread.is_alive():
                self.destroy()
                return
        else:
            try:
                self.worker.drain()
            finally:
                self.after(50, self._poll_worker)
            return
        self.after(50, self._poll_worker)

    def show_page(self, page_name):
        page = self.pages[page_name]

        if hasattr(page, "on_show"):
            page.on_show()

        page.tkraise()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.pages["Main"].cancel_sift()
        self.title("Closing — waiting for the current operation to finish...")
        self.worker.close()
        # Keep pumping Tk while the current message/login finishes safely.



if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
