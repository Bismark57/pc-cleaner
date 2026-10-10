"""Disk Cleanup tab: fast threaded scanner over whitelisted safe paths."""

import ctypes
import os
import shutil
import threading
import tkinter.messagebox as messagebox

import customtkinter as ctk

from .utils import expand, human_size, is_windows, safe_startswith

# ---------------------------------------------------------------------------
# Category definitions. ONLY paths listed here are ever scanned or deleted.
# Nothing outside these roots is touched, ever.
# ---------------------------------------------------------------------------

def _local_appdata():
    return expand(r"%LOCALAPPDATA%")


def build_categories():
    cats = [
        {
            "key": "win_temp",
            "name": "Windows Temp Files",
            "desc": "Leftover files in C:\\Windows\\Temp",
            "paths": [r"C:\Windows\Temp"],
        },
        {
            "key": "user_temp",
            "name": "User Temp Files",
            "desc": "Leftover files in your personal Temp folder",
            "paths": [expand(r"%TEMP%")],
        },
        {
            "key": "recycle",
            "name": "Recycle Bin",
            "desc": "Files you already deleted",
            "special": "recycle",
            "paths": [r"C:\$Recycle.Bin"],
        },
        {
            "key": "prefetch",
            "name": "Prefetch Files",
            "desc": "Old app launch cache (Windows rebuilds it)",
            "paths": [r"C:\Windows\Prefetch"],
        },
        {
            "key": "thumbcache",
            "name": "Thumbnail Cache",
            "desc": "Cached picture thumbnails",
            "paths": [os.path.join(_local_appdata(),
                                   r"Microsoft\Windows\Explorer")],
            "patterns": ("thumbcache_*.db", "iconcache_*.db"),
        },
        {
            "key": "delivery_opt",
            "name": "Delivery Optimization Files",
            "desc": "Downloaded update sharing files",
            "paths": [r"C:\Windows\SoftwareDistribution\DeliveryOptimization"],
        },
        {
            "key": "wu_download",
            "name": "Windows Update Cleanup",
            "desc": "Old downloaded Windows updates",
            "paths": [r"C:\Windows\SoftwareDistribution\Download"],
        },
        {
            "key": "chrome",
            "name": "Chrome Cache",
            "desc": "Google Chrome web cache (close Chrome first for best results)",
            "paths": [os.path.join(_local_appdata(),
                                    r"Google\Chrome\User Data\Default\Cache"),
                       os.path.join(_local_appdata(),
                                    r"Google\Chrome\User Data\Default\Code Cache")],
        },
        {
            "key": "edge",
            "name": "Edge Cache",
            "desc": "Microsoft Edge web cache (close Edge first for best results)",
            "paths": [os.path.join(_local_appdata(),
                                    r"Microsoft\Edge\User Data\Default\Cache"),
                       os.path.join(_local_appdata(),
                                    r"Microsoft\Edge\User Data\Default\Code Cache")],
        },
    ]
    # Drop categories whose roots don't exist on this machine.
    live = []
    for cat in cats:
        if cat.get("special") == "recycle":
            live.append(cat)
            continue
        existing = [p for p in cat["paths"] if os.path.isdir(p)]
        if existing:
            cat["paths"] = existing
            live.append(cat)
    return live


# ---------------------------------------------------------------------------
# Scanning / cleaning engine (no GUI code here)
# ---------------------------------------------------------------------------

class Cancelled(Exception):
    pass


def _iter_files(root, stop_event, patterns=None):
    """Yield file paths under root without following symlinks."""
    import fnmatch
    stack = [root]
    while stack:
        if stop_event.is_set():
            raise Cancelled()
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    if patterns:
                        name = entry.name.lower()
                        if not any(fnmatch.fnmatch(name, p.lower())
                                   for p in patterns):
                            continue
                    yield entry.path
            except OSError:
                continue


def scan_category(cat, stop_event):
    """Return (bytes, file_count) for a category."""
    total = 0
    count = 0
    for root in cat["paths"]:
        if not os.path.isdir(root):
            continue
        patterns = cat.get("patterns")
        try:
            for path in _iter_files(root, stop_event, patterns):
                try:
                    total += os.path.getsize(path)
                    count += 1
                except OSError:
                    continue
        except Cancelled:
            raise
    return total, count


def _delete_path(path, roots, log_fn):
    """Delete one file if it is inside a whitelisted root. Returns bytes freed."""
    if not safe_startswith(path, roots):
        return 0
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    try:
        os.remove(path)
        return size
    except OSError as exc:
        log_fn("  skipped (in use): %s" % os.path.basename(path))
        return 0


def empty_recycle_bin(log_fn):
    """Empty the Recycle Bin via Shell API. Returns True on success."""
    try:
        SHERB_NOCONFIRMATION = 0x1
        SHERB_NOPROGRESSUI = 0x2
        SHERB_NOSOUND = 0x4
        rc = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None,
            SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
        if rc == 0:
            log_fn("Recycle Bin emptied.")
            return True
        log_fn("Recycle Bin: nothing to empty or failed (code %d)." % rc)
        return rc == 0
    except Exception as exc:
        log_fn("Recycle Bin failed: %s" % exc)
        return False


def clean_category(cat, stop_event, log_fn, progress_fn):
    """Delete everything found by the scanner for one category."""
    freed = 0
    files = 0
    if cat.get("special") == "recycle":
        empty_recycle_bin(log_fn)
        return 0, 0
    roots = cat["paths"]
    # Collect first (fast), then delete with progress.
    targets = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for path in _iter_files(root, stop_event, cat.get("patterns")):
                targets.append(path)
        except Cancelled:
            raise
    total = len(targets)
    for i, path in enumerate(targets):
        if stop_event.is_set():
            raise Cancelled()
        freed += _delete_path(path, roots, log_fn)
        files += 1
        if total:
            progress_fn(i + 1, total)
    # Remove now-empty subdirectories (never the roots themselves).
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            if stop_event.is_set():
                raise Cancelled()
            if os.path.abspath(dirpath) == os.path.abspath(root):
                continue
            if not safe_startswith(dirpath, roots):
                continue
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
            except OSError:
                pass
    return freed, files


# ---------------------------------------------------------------------------
# GUI tab
# ---------------------------------------------------------------------------

class CleanupTab(ctk.CTkFrame):
    def __init__(self, master, log):
        super().__init__(master)
        self.log = log
        self.categories = build_categories()
        self.scan_results = {}      # key -> (bytes, count)
        self.rows = {}              # key -> dict of widgets
        self.scanning = False
        self.cleaning = False
        self.stop_event = threading.Event()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(self, text="Disk Cleanup",
                              font=ctk.CTkFont(size=20, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        sub = ctk.CTkLabel(
            self,
            text="Scans only safe junk-file locations. Nothing else is touched.",
            font=ctk.CTkFont(size=13), text_color="gray")
        sub.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        # Category list
        self.list_frame = ctk.CTkScrollableFrame(self, height=280)
        self.list_frame.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        self.list_frame.grid_columnconfigure(1, weight=1)
        for idx, cat in enumerate(self.categories):
            self._make_row(idx, cat)

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        ctrl.grid_columnconfigure(2, weight=1)

        self.scan_btn = ctk.CTkButton(ctrl, text="Scan Now", width=160,
                                      height=44, command=self.start_scan)
        self.scan_btn.grid(row=0, column=0, padx=(0, 10))

        self.clean_btn = ctk.CTkButton(ctrl, text="Clean Selected", width=160,
                                       height=44, command=self.start_clean,
                                       state="disabled", fg_color="#b3402e",
                                       hover_color="#93331f")
        self.clean_btn.grid(row=0, column=1, padx=10)

        self.total_label = ctk.CTkLabel(ctrl, text="Total: not scanned yet",
                                        font=ctk.CTkFont(size=15,
                                                         weight="bold"))
        self.total_label.grid(row=0, column=2, sticky="e")

        self.progress = ctk.CTkProgressBar(self, width=500, height=14)
        self.progress.grid(row=4, column=0, padx=20, pady=(0, 6),
                           sticky="ew")
        self.progress.set(0)

        self.status = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=13),
                                   text_color="gray")
        self.status.grid(row=5, column=0, padx=20, pady=(0, 16), sticky="w")

    def _make_row(self, idx, cat):
        var = ctk.BooleanVar(value=True)
        chk = ctk.CTkCheckBox(self.list_frame, text="", variable=var,
                              width=30)
        chk.grid(row=idx, column=0, padx=(10, 4), pady=10, sticky="w")
        name = ctk.CTkLabel(self.list_frame, text=cat["name"],
                            font=ctk.CTkFont(size=14, weight="bold"),
                            anchor="w")
        name.grid(row=idx, column=1, padx=4, pady=(10, 0), sticky="w")
        desc = ctk.CTkLabel(self.list_frame, text=cat["desc"],
                            font=ctk.CTkFont(size=12), text_color="gray",
                            anchor="w")
        desc.grid(row=idx, column=1, padx=4, pady=(0, 10), sticky="w")
        size = ctk.CTkLabel(self.list_frame, text="—",
                            font=ctk.CTkFont(size=14), width=110,
                            anchor="e")
        size.grid(row=idx, column=2, padx=10, pady=10, sticky="e")
        self.rows[cat["key"]] = {"var": var, "size": size, "cat": cat}

    # -- scanning ---------------------------------------------------------
    def start_scan(self):
        if self.scanning or self.cleaning:
            return
        self.scanning = True
        self.stop_event.clear()
        self.scan_results = {}
        self.scan_btn.configure(state="disabled", text="Scanning… (click to stop)")
        self.scan_btn.configure(command=self.stop_work)
        self.clean_btn.configure(state="disabled")
        self.progress.set(0)
        self.status.configure(text="Scanning…")
        for row in self.rows.values():
            row["size"].configure(text="…")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            total_bytes = 0
            n = len(self.categories)
            for i, cat in enumerate(self.categories):
                if self.stop_event.is_set():
                    raise Cancelled()
                self.after(0, self.status.configure,
                           {"text": "Scanning: %s" % cat["name"]})
                size, count = scan_category(cat, self.stop_event)
                self.scan_results[cat["key"]] = (size, count)
                total_bytes += size
                key = cat["key"]
                self.after(0, self._update_row_size, key, size, count)
                self.after(0, self.progress.set, (i + 1) / n)
            self.after(0, self._scan_done, total_bytes, False)
        except Cancelled:
            self.after(0, self._scan_done, 0, True)
        except Exception as exc:
            self.after(0, self._scan_error, str(exc))

    def _update_row_size(self, key, size, count):
        row = self.rows.get(key)
        if row:
            row["size"].configure(text=human_size(size))

    def _scan_done(self, total_bytes, cancelled):
        self.scanning = False
        self.scan_btn.configure(state="normal", text="Scan Now",
                                command=self.start_scan)
        self.progress.set(0)
        if cancelled:
            self.status.configure(text="Scan cancelled.")
            self.log("Disk scan cancelled by user.")
            return
        self.total_label.configure(
            text="Total reclaimable: %s" % human_size(total_bytes))
        self.status.configure(text="Scan complete.")
        self.clean_btn.configure(state="normal")
        self.log("Disk scan complete. Reclaimable: %s."
                 % human_size(total_bytes))

    def _scan_error(self, msg):
        self.scanning = False
        self.scan_btn.configure(state="normal", text="Scan Now",
                                command=self.start_scan)
        self.status.configure(text="Scan failed.")
        self.log("Disk scan failed: %s" % msg)
        messagebox.showerror("Scan failed",
                             "Something went wrong during the scan:\n%s" % msg)

    def stop_work(self):
        self.stop_event.set()
        self.status.configure(text="Stopping…")

    # -- cleaning ---------------------------------------------------------
    def start_clean(self):
        if self.scanning or self.cleaning:
            return
        selected = [row["cat"] for row in self.rows.values()
                    if row["var"].get() and row["cat"]["key"] in self.scan_results]
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one category first.")
            return
        total = sum(self.scan_results[c["key"]][0] for c in selected)
        if not messagebox.askyesno(
                "Confirm cleanup",
                "Delete %s of junk files?\n\nThis only removes files in the "
                "safe locations listed above. This cannot be undone." %
                human_size(total)):
            return
        self.cleaning = True
        self.stop_event.clear()
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled", text="Cleaning…")
        self.progress.set(0)
        threading.Thread(target=self._clean_worker, args=(selected,),
                         daemon=True).start()

    def _clean_worker(self, selected):
        try:
            grand_freed = 0
            grand_files = 0
            for idx, cat in enumerate(selected):
                if self.stop_event.is_set():
                    raise Cancelled()
                self.after(0, self.status.configure,
                           {"text": "Cleaning: %s" % cat["name"]})
                self.log("Cleaning %s…" % cat["name"])

                def prog(done, total, _idx=idx):
                    frac = (_idx + (done / total if total else 1)) / len(selected)
                    self.after(0, self.progress.set, frac)

                freed, files = clean_category(cat, self.stop_event,
                                              self.log, prog)
                grand_freed += freed
                grand_files += files
                key = cat["key"]
                self.after(0, self._update_row_size, key, 0, 0)
                self.scan_results[key] = (0, 0)
            self.after(0, self._clean_done, grand_freed, grand_files, False)
        except Cancelled:
            self.after(0, self._clean_done, 0, 0, True)
        except Exception as exc:
            self.after(0, self._scan_error, str(exc))
            self.after(0, self.clean_btn.configure,
                       {"state": "normal", "text": "Clean Selected"})
            self.cleaning = False

    def _clean_done(self, freed, files, cancelled):
        self.cleaning = False
        self.scan_btn.configure(state="normal")
        self.clean_btn.configure(state="normal", text="Clean Selected")
        self.progress.set(0)
        if cancelled:
            self.status.configure(text="Cleanup cancelled.")
            self.log("Cleanup cancelled by user.")
            return
        remaining = sum(v[0] for v in self.scan_results.values())
        self.total_label.configure(
            text="Total reclaimable: %s" % human_size(remaining))
        self.status.configure(text="Cleanup complete.")
        self.log("Cleanup complete. Freed %s (%d files)."
                 % (human_size(freed), files))
        messagebox.showinfo("Cleanup complete",
                            "Freed %s across %d files." %
                            (human_size(freed), files))
