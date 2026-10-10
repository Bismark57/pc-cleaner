"""Dashboard tab: system overview (OS, CPU, RAM, disk)."""

import platform
import shutil
import threading
import tkinter.messagebox as messagebox

import customtkinter as ctk

from .utils import human_size, is_windows


def _windows_product_name():
    if not is_windows():
        return platform.system()
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        name, _ = winreg.QueryValueEx(key, "ProductName")
        build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        winreg.CloseKey(key)
        return "%s (build %s)" % (name, build)
    except Exception:
        return "%s %s" % (platform.system(), platform.release())


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, log):
        super().__init__(master)
        self.log = log

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="System Overview",
                             font=ctk.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.info = ctk.CTkLabel(self, text="Loading...", justify="left",
                                 font=ctk.CTkFont(size=14))
        self.info.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        disk_label = ctk.CTkLabel(self, text="Drive C: usage",
                                  font=ctk.CTkFont(size=14, weight="bold"))
        disk_label.grid(row=2, column=0, padx=20, pady=(10, 4), sticky="w")

        self.disk_bar = ctk.CTkProgressBar(self, width=420, height=20)
        self.disk_bar.grid(row=3, column=0, padx=20, pady=4, sticky="w")
        self.disk_bar.set(0)

        self.disk_text = ctk.CTkLabel(self, text="", justify="left",
                                      font=ctk.CTkFont(size=13))
        self.disk_text.grid(row=4, column=0, padx=20, pady=4, sticky="w")

        self.refresh_btn = ctk.CTkButton(self, text="Refresh",
                                        width=160, height=40,
                                        command=self.refresh)
        self.refresh_btn.grid(row=5, column=0, padx=20, pady=20, sticky="w")

        self.refresh()

    def refresh(self):
        self.refresh_btn.configure(state="disabled")
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            lines = []
            lines.append("Operating system:  %s" % _windows_product_name())
            lines.append("Computer:  %s" % platform.node())
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                lines.append("CPU usage:  %d%%  (%d cores)" %
                             (cpu, psutil.cpu_count(logical=True)))
                lines.append("Memory:  %s used of %s  (%d%%)" %
                             (human_size(mem.used), human_size(mem.total),
                              mem.percent))
            except Exception as exc:
                lines.append("CPU/Memory info unavailable (%s)" % exc)

            try:
                usage = shutil.disk_usage("C:\\")
                used = usage.used
                total = usage.total
                free = usage.free
                pct = used / total if total else 0
                disk_summary = ("%s used of %s  (%d%%)\n%s free" %
                                (human_size(used), human_size(total),
                                 int(pct * 100), human_size(free)))
            except Exception as exc:
                used = total = 0
                pct = 0
                disk_summary = "Drive info unavailable (%s)" % exc

            info_text = "\n".join(lines)
            self.after(0, self._update_ui, info_text, disk_summary, pct)
        except Exception as exc:
            self.after(0, self._update_ui,
                       "Could not load system info:\n%s" % exc, "", 0)

    def _update_ui(self, info_text, disk_summary, pct):
        self.info.configure(text=info_text)
        self.disk_bar.set(pct)
        self.disk_text.configure(text=disk_summary)
        self.refresh_btn.configure(state="normal")
        self.log("Dashboard refreshed.")
