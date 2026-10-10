"""Drivers tab: list installed drivers (WMI) and check Windows Update."""

import json
import re
import threading
import tkinter.messagebox as messagebox

import customtkinter as ctk

from .utils import is_admin, run_powershell

DRIVER_LIST_PS = r"""
$items = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceName -and $_.DeviceName.Trim() -ne '' } |
    Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer, DeviceID
$items | ConvertTo-Json -Depth 2 -Compress
"""

DRIVER_SEARCH_PS = r"""
$ErrorActionPreference = 'Stop'
Write-Output 'Opening Windows Update searcher (this can take a few minutes)...'
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search("IsInstalled=0 and Type='Driver'")
Write-Output ("FOUND_COUNT=" + $result.Updates.Count)
foreach ($u in $result.Updates) {
    Write-Output ("UPDATE_TITLE=" + $u.Title)
}
"""

DRIVER_INSTALL_PS = r"""
$ErrorActionPreference = 'Stop'
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
Write-Output 'Searching for driver updates...'
$result = $searcher.Search("IsInstalled=0 and Type='Driver'")
if ($result.Updates.Count -eq 0) {
    Write-Output 'No driver updates available.'
    exit 0
}
Write-Output ("Found " + $result.Updates.Count + " driver update(s). Downloading...")
$coll = New-Object -ComObject Microsoft.Update.UpdateColl
foreach ($u in $result.Updates) { [void]$coll.Add($u) }
$downloader = $session.CreateUpdateDownloader()
$downloader.Updates = $coll
$dl = $downloader.Download()
Write-Output ("Download result code: " + $dl.ResultCode + " (2 = succeeded)")
Write-Output 'Installing...'
$installer = $session.CreateUpdateInstaller()
$installer.Updates = $coll
$ir = $installer.Install()
Write-Output ("Install result code: " + $ir.ResultCode + " (2 = succeeded)")
Write-Output ("Reboot required: " + $ir.RebootRequired)
"""


def parse_wmi_date(value):
    """Parse WMI datetime or /Date(ms)/ into YYYY-MM-DD."""
    if not value:
        return "—"
    s = str(value)
    m = re.match(r"/Date\((\d+)", s)
    if m:
        import datetime
        try:
            dt = datetime.datetime.fromtimestamp(int(m.group(1)) / 1000)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return "—"
    m = re.match(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    return s[:10]


class DriversTab(ctk.CTkFrame):
    def __init__(self, master, log):
        super().__init__(master)
        self.log = log
        self.drivers = []
        self.busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(self, text="Device Drivers",
                              font=ctk.CTkFont(size=20, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        sub = ctk.CTkLabel(
            self,
            text="See every installed driver. Check Windows Update for newer ones.",
            font=ctk.CTkFont(size=13), text_color="gray")
        sub.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(self, height=300)
        self.list_frame.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=3, column=0, padx=20, pady=8, sticky="ew")

        self.refresh_btn = ctk.CTkButton(ctrl, text="Refresh Driver List",
                                         width=180, height=44,
                                         command=self.refresh_list)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))

        self.check_btn = ctk.CTkButton(ctrl, text="Check for Driver Updates",
                                       width=200, height=44,
                                       command=self.check_updates)
        self.check_btn.grid(row=0, column=1, padx=10)

        self.install_btn = ctk.CTkButton(ctrl, text="Install Driver Updates",
                                         width=200, height=44,
                                         command=self.install_updates,
                                         fg_color="#2e7d32",
                                         hover_color="#1f5c23",
                                         state="disabled")
        self.install_btn.grid(row=0, column=2, padx=10)

        self.status = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=13),
                                   text_color="gray")
        self.status.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="w")

        upd_label = ctk.CTkLabel(self, text="Available driver updates:",
                                 font=ctk.CTkFont(size=14, weight="bold"))
        upd_label.grid(row=5, column=0, padx=20, pady=(4, 4), sticky="w")

        self.updates_box = ctk.CTkTextbox(self, height=110, state="disabled")
        self.updates_box.grid(row=6, column=0, padx=20, pady=(0, 16),
                              sticky="ew")

        self.refresh_list()

    # -- driver list ------------------------------------------------------
    def refresh_list(self):
        if self.busy:
            return
        self.busy = True
        self.refresh_btn.configure(state="disabled")
        self.status.configure(text="Reading installed drivers…")
        threading.Thread(target=self._list_worker, daemon=True).start()

    def _list_worker(self):
        try:
            proc = run_powershell(DRIVER_LIST_PS, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "WMI query failed")
            data = json.loads(proc.stdout) if proc.stdout.strip() else []
            if isinstance(data, dict):
                data = [data]
            seen = set()
            drivers = []
            for d in data:
                dev_id = d.get("DeviceID") or d.get("DeviceName")
                if dev_id in seen:
                    continue
                seen.add(dev_id)
                drivers.append({
                    "name": d.get("DeviceName") or "Unknown device",
                    "version": d.get("DriverVersion") or "—",
                    "date": parse_wmi_date(d.get("DriverDate")),
                    "maker": d.get("Manufacturer") or "",
                })
            drivers.sort(key=lambda x: x["name"].lower())
            self.drivers = drivers
            self.after(0, self._render_list)
        except Exception as exc:
            self.after(0, self._list_error, str(exc))

    def _render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        for i, d in enumerate(self.drivers):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", padx=6, pady=4)
            row.grid_columnconfigure(0, weight=1)
            name = ctk.CTkLabel(row, text=d["name"], anchor="w",
                                font=ctk.CTkFont(size=13, weight="bold"))
            name.grid(row=0, column=0, sticky="w")
            detail = ctk.CTkLabel(
                row,
                text="Version %s   •   Date %s%s" %
                     (d["version"], d["date"],
                      ("   •   " + d["maker"]) if d["maker"] else ""),
                anchor="w", font=ctk.CTkFont(size=12), text_color="gray")
            detail.grid(row=1, column=0, sticky="w")
        self.busy = False
        self.refresh_btn.configure(state="normal")
        self.status.configure(text="%d drivers found." % len(self.drivers))
        self.log("Driver list refreshed: %d devices." % len(self.drivers))

    def _list_error(self, msg):
        self.busy = False
        self.refresh_btn.configure(state="normal")
        self.status.configure(text="Could not read drivers.")
        self.log("Driver list failed: %s" % msg)
        messagebox.showerror("Driver list failed",
                             "Could not read installed drivers:\n%s" % msg)

    # -- update check ------------------------------------------------------
    def check_updates(self):
        if self.busy:
            return
        self.busy = True
        self.check_btn.configure(state="disabled")
        self.install_btn.configure(state="disabled")
        self.status.configure(text="Asking Windows Update… (can take minutes)")
        self._set_updates_text("Searching Windows Update for driver updates…\n"
                               "This can take a few minutes. Please wait.")
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            proc = run_powershell(DRIVER_SEARCH_PS, timeout=900)
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            titles = []
            count = 0
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("FOUND_COUNT="):
                    try:
                        count = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("UPDATE_TITLE="):
                    titles.append(line.split("=", 1)[1])
            self.after(0, self._check_done, count, titles, output)
        except Exception as exc:
            self.after(0, self._check_error, str(exc))

    def _check_done(self, count, titles, output):
        self.busy = False
        self.check_btn.configure(state="normal")
        if count > 0:
            text = "%d driver update(s) available:\n\n" % count + \
                "\n".join("• " + t for t in titles)
            self.install_btn.configure(state="normal")
            self.status.configure(text="%d driver update(s) available." % count)
            self.log("Windows Update reports %d driver update(s)." % count)
        else:
            text = "All drivers are up to date. 🎉"
            self.status.configure(text="All drivers up to date.")
            self.log("Driver check: everything up to date.")
        self._set_updates_text(text)

    def _check_error(self, msg):
        self.busy = False
        self.check_btn.configure(state="normal")
        self.status.configure(text="Update check failed.")
        self._set_updates_text("Check failed:\n%s" % msg)
        self.log("Driver update check failed: %s" % msg)
        messagebox.showerror("Update check failed",
                             "Could not query Windows Update:\n%s" % msg)

    def _set_updates_text(self, text):
        self.updates_box.configure(state="normal")
        self.updates_box.delete("1.0", "end")
        self.updates_box.insert("1.0", text)
        self.updates_box.configure(state="disabled")

    # -- install -----------------------------------------------------------
    def install_updates(self):
        if self.busy:
            return
        if not is_admin():
            messagebox.showwarning(
                "Administrator needed",
                "Installing driver updates needs administrator rights.\n"
                "Please restart PC Cleaner as administrator.")
            return
        if not messagebox.askyesno(
                "Install driver updates?",
                "Download and install all available driver updates?\n\n"
                "Your PC may need a restart afterwards. Save your work first."):
            return
        self.busy = True
        self.install_btn.configure(state="disabled")
        self.check_btn.configure(state="disabled")
        self.status.configure(text="Installing driver updates…")
        self._set_updates_text("Installing… watch the log below for progress.")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        try:
            proc = run_powershell(DRIVER_INSTALL_PS, timeout=3600)
            output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            self.after(0, self._install_done, output)
        except Exception as exc:
            self.after(0, self._install_error, str(exc))

    def _install_error(self, msg):
        self.busy = False
        self.check_btn.configure(state="normal")
        self.install_btn.configure(state="normal")
        self.status.configure(text="Install failed.")
        self._set_updates_text("Install failed:\n%s" % msg)
        self.log("Driver install failed: %s" % msg)
        messagebox.showerror("Install failed",
                             "Could not install driver updates:\n%s" % msg)

    def _install_done(self, output):
        self.busy = False
        self.check_btn.configure(state="normal")
        self._set_updates_text("Install finished. Details in the log below.")
        for line in output.splitlines():
            line = line.strip()
            if line:
                self.log("[drivers] " + line)
        self.status.configure(text="Install finished — see log.")
        if "Reboot required: True" in output:
            messagebox.showinfo(
                "Restart needed",
                "Driver updates installed. Please restart your PC to finish.")
        else:
            messagebox.showinfo("Done", "Driver update installation finished.")
