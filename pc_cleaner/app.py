"""PC Cleaner main window."""

import datetime
import sys
import tkinter.messagebox as messagebox

import customtkinter as ctk

from . import __version__
from .cleaner import CleanupTab
from .dashboard import DashboardTab
from .drivers import DriversTab
from .software import SoftwareTab
from .utils import is_admin, is_windows, relaunch_as_admin


class PCCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("PC Cleaner v%s" % __version__)
        self.geometry("860x720")
        self.minsize(780, 640)

        self.grid_columnconfigure(0, weight=1)

        # Admin banner (the installed exe requests admin via manifest,
        # but show this when running without elevation, e.g. from source).
        if is_windows() and not is_admin():
            banner = ctk.CTkFrame(self, fg_color="#7a4a12")
            banner.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
            banner.grid_columnconfigure(0, weight=1)
            lbl = ctk.CTkLabel(
                banner,
                text="Not running as administrator — driver installs and "
                     "some cleanup need admin rights.",
                font=ctk.CTkFont(size=13))
            lbl.grid(row=0, column=0, padx=12, pady=8, sticky="w")
            btn = ctk.CTkButton(banner, text="Restart as Administrator",
                                width=200, command=self._restart_admin)
            btn.grid(row=0, column=1, padx=12, pady=8)
            tabs_row = 1
        else:
            tabs_row = 0

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=tabs_row + 1, column=0, padx=10, pady=10,
                       sticky="nsew")
        self.grid_rowconfigure(tabs_row + 1, weight=1)
        for name in ("Dashboard", "Disk Cleanup", "Drivers", "Software"):
            self.tabs.add(name)
            self.tabs.tab(name).grid_columnconfigure(0, weight=1)
            self.tabs.tab(name).grid_rowconfigure(0, weight=1)

        for name, cls in (("Dashboard", DashboardTab),
                          ("Disk Cleanup", CleanupTab),
                          ("Drivers", DriversTab),
                          ("Software", SoftwareTab)):
            frame = cls(self.tabs.tab(name), self.log)
            frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Shared log window
        log_label = ctk.CTkLabel(self, text="Activity log",
                                 font=ctk.CTkFont(size=13, weight="bold"))
        log_label.grid(row=tabs_row + 2, column=0, padx=14, pady=(0, 2),
                       sticky="w")
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=tabs_row + 3, column=0, padx=10, pady=(0, 10),
                       sticky="ew")
        log_frame.grid_columnconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(log_frame, height=90, state="disabled")
        self.log_box.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        clear_btn = ctk.CTkButton(log_frame, text="Clear", width=80,
                                  command=self._clear_log)
        clear_btn.grid(row=0, column=1, padx=(0, 8), pady=8)

        self.log("PC Cleaner v%s started." % __version__)
        if is_windows() and not is_admin():
            self.log("Running without administrator rights.")

    def _restart_admin(self):
        try:
            relaunch_as_admin()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Elevation failed", str(exc))

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def log(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s\n" % (stamp, message)

        def _write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        try:
            self.after(0, _write)
        except Exception:
            pass


def main():
    if not is_windows():
        # Allow import-time checks on other platforms, but the app itself
        # only makes sense on Windows.
        print("PC Cleaner is a Windows application.", file=sys.stderr)
        return 1
    app = PCCleanerApp()
    app.mainloop()
    return 0
