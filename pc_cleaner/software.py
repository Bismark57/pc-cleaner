"""Software tab: list and install app updates via winget."""

import re
import subprocess
import threading
import tkinter.messagebox as messagebox

import customtkinter as ctk

from .utils import is_admin


def winget_available():
    try:
        proc = subprocess.run(["winget", "--version"],
                              capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def parse_winget_upgrade(output):
    """Parse `winget upgrade` table output into a list of dicts."""
    upgrades = []
    lines = output.splitlines()
    # Find the header separator (a line of dashes).
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^[-\s]+$", line) and len(line.strip()) > 5:
            start = i + 1
            break
    if start is None:
        return upgrades
    for line in lines[start:]:
        if not line.strip():
            continue
        # Columns are separated by 2+ spaces; the name itself may contain
        # single spaces, and the Id never contains spaces.
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 4:
            continue
        name = parts[0].strip()
        pkg_id = parts[1].strip()
        current = parts[2].strip() if len(parts) > 2 else ""
        available = parts[3].strip() if len(parts) > 3 else ""
        if not pkg_id or pkg_id.lower() in ("id",):
            continue
        upgrades.append({"name": name, "id": pkg_id,
                         "current": current, "available": available})
    return upgrades


class SoftwareTab(ctk.CTkFrame):
    def __init__(self, master, log):
        super().__init__(master)
        self.log = log
        self.upgrades = []
        self.checks = {}   # pkg_id -> BooleanVar
        self.busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(self, text="Software Updates",
                              font=ctk.CTkFont(size=20, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        sub = ctk.CTkLabel(
            self,
            text="Find updates for your installed apps (via Windows winget).",
            font=ctk.CTkFont(size=13), text_color="gray")
        sub.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(self, height=260)
        self.list_frame.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        self.list_frame.grid_columnconfigure(1, weight=1)

        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=3, column=0, padx=20, pady=8, sticky="ew")

        self.refresh_btn = ctk.CTkButton(ctrl, text="Check for Updates",
                                         width=170, height=44,
                                         command=self.refresh)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))

        self.sel_btn = ctk.CTkButton(ctrl, text="Update Selected",
                                     width=170, height=44,
                                     command=self.update_selected,
                                     fg_color="#2e7d32", hover_color="#1f5c23",
                                     state="disabled")
        self.sel_btn.grid(row=0, column=1, padx=10)

        self.all_btn = ctk.CTkButton(ctrl, text="Update All", width=150,
                                     height=44, command=self.update_all,
                                     fg_color="#2e7d32", hover_color="#1f5c23",
                                     state="disabled")
        self.all_btn.grid(row=0, column=2, padx=10)

        self.status = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=13),
                                   text_color="gray")
        self.status.grid(row=4, column=0, padx=20, pady=(0, 4), sticky="w")

        out_label = ctk.CTkLabel(self, text="Progress:",
                                 font=ctk.CTkFont(size=14, weight="bold"))
        out_label.grid(row=5, column=0, padx=20, pady=(4, 4), sticky="w")
        self.out_box = ctk.CTkTextbox(self, height=110)
        self.out_box.grid(row=6, column=0, padx=20, pady=(0, 16), sticky="ew")

        self.refresh()

    # -- listing ----------------------------------------------------------
    def refresh(self):
        if self.busy:
            return
        if not winget_available():
            self.status.configure(text="winget not found on this PC.")
            self.log("winget is not installed or not on PATH.")
            messagebox.showwarning(
                "winget not found",
                "Windows Package Manager (winget) was not found.\n"
                "It comes with Windows 10/11 via the Microsoft Store\n"
                "('App Installer'). Update that app, then try again.")
            return
        self.busy = True
        self.refresh_btn.configure(state="disabled")
        self.sel_btn.configure(state="disabled")
        self.all_btn.configure(state="disabled")
        self.status.configure(text="Checking for software updates…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            proc = subprocess.run(
                ["winget", "upgrade"], capture_output=True, text=True,
                timeout=600, encoding="utf-8", errors="replace")
            upgrades = parse_winget_upgrade(proc.stdout or "")
            self.upgrades = upgrades
            self.after(0, self._render_list)
        except Exception as exc:
            self.after(0, self._refresh_error, str(exc))

    def _render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.checks = {}
        if not self.upgrades:
            lbl = ctk.CTkLabel(self.list_frame,
                               text="All your apps are up to date. 🎉",
                               font=ctk.CTkFont(size=14))
            lbl.grid(row=0, column=0, padx=20, pady=20)
        for i, app in enumerate(self.upgrades):
            var = ctk.BooleanVar(value=True)
            self.checks[app["id"]] = var
            chk = ctk.CTkCheckBox(self.list_frame, text="", variable=var,
                                  width=30)
            chk.grid(row=i, column=0, padx=(10, 4), pady=10, sticky="w")
            name = ctk.CTkLabel(self.list_frame, text=app["name"], anchor="w",
                                font=ctk.CTkFont(size=13, weight="bold"))
            name.grid(row=i, column=1, padx=4, pady=(10, 0), sticky="w")
            ver = ctk.CTkLabel(
                self.list_frame,
                text="%s  →  %s" % (app["current"], app["available"]),
                anchor="w", font=ctk.CTkFont(size=12), text_color="gray")
            ver.grid(row=i, column=1, padx=4, pady=(0, 10), sticky="w")
        self.busy = False
        self.refresh_btn.configure(state="normal")
        has = bool(self.upgrades)
        self.sel_btn.configure(state="normal" if has else "disabled")
        self.all_btn.configure(state="normal" if has else "disabled")
        self.status.configure(
            text="%d update(s) available." % len(self.upgrades)
            if has else "Everything is up to date.")
        self.log("Software check: %d update(s) available."
                 % len(self.upgrades))

    def _refresh_error(self, msg):
        self.busy = False
        self.refresh_btn.configure(state="normal")
        self.status.configure(text="Check failed.")
        self.log("Software check failed: %s" % msg)
        messagebox.showerror("Check failed",
                             "Could not check for updates:\n%s" % msg)

    # -- updating ----------------------------------------------------------
    def _selected_ids(self):
        return [pid for pid, var in self.checks.items() if var.get()]

    def update_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one app first.")
            return
        if not self._confirm(len(ids)):
            return
        self._run_updates(ids)

    def update_all(self):
        ids = [a["id"] for a in self.upgrades]
        if not ids:
            return
        if not self._confirm(len(ids)):
            return
        self._run_updates(ids)

    def _confirm(self, n):
        extra = "" if is_admin() else \
            "\n\nNote: not running as administrator — some updates may fail."
        return messagebox.askyesno(
            "Install updates?",
            "Download and install %d app update(s)?%s" % (n, extra))

    def _run_updates(self, ids):
        if self.busy:
            return
        self.busy = True
        self.refresh_btn.configure(state="disabled")
        self.sel_btn.configure(state="disabled")
        self.all_btn.configure(state="disabled")
        self._out_clear()
        self._out_write("Updating %d app(s)…\n" % len(ids))
        threading.Thread(target=self._update_worker, args=(ids,),
                         daemon=True).start()

    def _update_worker(self, ids):
        ok = 0
        for pkg_id in ids:
            self.after(0, self.status.configure,
                       {"text": "Updating: %s" % pkg_id})
            self.after(0, self._out_write, "\n=== %s ===\n" % pkg_id)
            self.log("Updating %s…" % pkg_id)
            try:
                proc = subprocess.Popen(
                    ["winget", "upgrade", "--id", pkg_id, "--silent",
                     "--accept-package-agreements",
                     "--accept-source-agreements"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace")
                for line in proc.stdout:
                    self.after(0, self._out_write, line)
                proc.wait(timeout=1800)
                if proc.returncode == 0:
                    ok += 1
                    self.after(0, self._out_write, "✔ Done: %s\n" % pkg_id)
                    self.log("Updated %s." % pkg_id)
                else:
                    self.after(0, self._out_write,
                               "✘ Failed (exit %d): %s\n"
                               % (proc.returncode, pkg_id))
                    self.log("Update failed for %s (exit %d)."
                             % (pkg_id, proc.returncode))
            except Exception as exc:
                self.after(0, self._out_write, "✘ Error: %s\n" % exc)
                self.log("Update error for %s: %s" % (pkg_id, exc))
        self.after(0, self._updates_done, ok, len(ids))

    def _updates_done(self, ok, total):
        self.busy = False
        self.refresh_btn.configure(state="normal")
        self.status.configure(text="Finished: %d of %d updated." % (ok, total))
        self._out_write("\nFinished: %d of %d updated.\n" % (ok, total))
        self.log("Software updates finished: %d of %d." % (ok, total))
        messagebox.showinfo("Updates finished",
                            "%d of %d app(s) updated." % (ok, total))
        self.refresh()

    def _out_write(self, text):
        self.out_box.insert("end", text)
        self.out_box.see("end")

    def _out_clear(self):
        self.out_box.delete("1.0", "end")
