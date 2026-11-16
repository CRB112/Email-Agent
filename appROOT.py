import ttkbootstrap as ttk
from tkinter import messagebox

from app.services.worker import BackgroundWorker
from app.pages.pages import PAGES_LIST
from app.parser.parser import loadUserOptions

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

        self.email_agent = None
        self.worker = BackgroundWorker()
        self.closing = False
        self.protocol("WM_DELETE_WINDOW", self.close)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {}

        try:
            loadUserOptions()
        except Exception as error:
            messagebox.showerror("Settings need repair", f"{error}\n\nYour settings were preserved. Repair ~/.config/EmailSiftingAgent/useroptions.json and restart.", parent=self)
            self.worker.close()
            self.destroy()
            raise SystemExit(1) from error

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

    def _poll_worker(self):
        if self.closing:
            self.worker.drain()
            if not self.worker.thread.is_alive():
                self.worker.drain()
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
    import sys
    if "--check-install" in sys.argv:
        from app.parser.parser import DEFAULT_OPTIONS_FILE
        from app.rules.validation import validate_options
        import json
        validate_options(json.loads(DEFAULT_OPTIONS_FILE.read_text(encoding="utf-8")))
        # Loading discovery from the packaged SDK catches missing Gmail data.
        from googleapiclient.discovery import build
        from google.auth.credentials import AnonymousCredentials
        client = build("gmail", "v1", credentials=AnonymousCredentials(), cache_discovery=False, static_discovery=True)
        client.close()
        print("Installation OK: providers, UI imports, Gmail discovery, bundled defaults.")
        raise SystemExit(0)
    app = MainWindow()
    app.mainloop()
