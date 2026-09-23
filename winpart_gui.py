#!/usr/bin/env python3

import json
import os
import pwd
import shlex
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk as ttk_std

# Optional modern theme support.
# If ttkbootstrap is installed, the app will use a modern dark theme.
# If not, it falls back to a manual dark Tkinter theme.
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    HAS_BOOTSTRAP = True
except Exception:
    ttk = ttk_std
    HAS_BOOTSTRAP = False


APP_NAME = "Windows Partition Manager"
APP_VERSION = "1.0.0"

DEFAULT_MOUNT_NAME = "WindowsPartitionMount"

# Windows-related filesystems.
# BitLocker is shown only to warn the user; it cannot be mounted as plain NTFS.
WIN_FSTYPES = {"ntfs", "ntfs3", "fuseblk", "bitlocker"}


def default_mountpoint():
    """
    Prefer a mount folder inside the normal user's home directory.

    This avoids confusion with /mnt/winpart and makes it clearer that
    the folder is only a mount point.
    """
    try:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            sudo_user = os.environ.get("SUDO_USER")
            if sudo_user:
                pw = pwd.getpwnam(sudo_user)
                return os.path.join(pw.pw_dir, DEFAULT_MOUNT_NAME)
    except Exception:
        pass

    return os.path.join(os.path.expanduser("~"), DEFAULT_MOUNT_NAME)


def cmd_str(cmd):
    return " ".join(shlex.quote(str(x)) for x in cmd)


def human_size(n):
    try:
        n = float(n)
    except Exception:
        return ""

    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if n < 1024.0 or unit == "PiB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0


def dir_icon():
    return "📁"


def file_icon(name):
    ext = os.path.splitext(name)[1].lower()

    if ext in {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp",
        ".webp", ".svg", ".ico", ".tif", ".tiff"
    }:
        return "🖼️"

    if ext in {
        ".mp3", ".wav", ".flac", ".ogg", ".m4a",
        ".aac", ".wma", ".opus"
    }:
        return "🎵"

    if ext in {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv",
        ".webm", ".m4v", ".mpg", ".mpeg"
    }:
        return "🎬"

    if ext in {
        ".zip", ".tar", ".gz", ".bz2", ".xz",
        ".7z", ".rar", ".zst"
    }:
        return "📦"

    if ext in {
        ".pdf"
    }:
        return "📕"

    if ext in {
        ".doc", ".docx", ".odt", ".txt", ".md",
        ".rtf", ".xls", ".xlsx", ".ods", ".ppt",
        ".pptx", ".csv"
    }:
        return "📄"

    if ext in {
        ".exe", ".msi", ".dll", ".sys", ".bat",
        ".cmd", ".ps1"
    }:
        return "⚙️"

    if ext in {
        ".iso", ".img", ".vhd", ".vhdx", ".wim"
    }:
        return "💿"

    if ext in {
        ".lnk"
    }:
        return "🔗"

    return "📄"


def create_button(parent, text, command, style="secondary"):
    """
    Create a button.

    If ttkbootstrap is available, use modern bootstyle.
    Otherwise use normal ttk.Button.
    """
    if HAS_BOOTSTRAP:
        return ttk.Button(parent, text=text, command=command, bootstyle=style)

    return ttk.Button(parent, text=text, command=command)


def apply_fallback_dark(root):
    """
    Apply a basic dark theme if ttkbootstrap is not available.
    """
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#1e1f22"
    fg = "#e8eaed"
    field = "#2b2d31"
    active = "#3a3b40"
    button = "#3c4043"
    button_active = "#4a4d51"

    root.configure(bg=bg)

    style.configure(
        ".",
        background=bg,
        foreground=fg,
        fieldbackground=field,
        bordercolor=bg,
        troughcolor=bg,
        focuscolor=bg,
    )

    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)

    style.configure("TButton", background=button, foreground=fg, padding=6)
    style.map("TButton", background=[("active", button_active)])

    style.configure(
        "TNotebook",
        background=bg,
        bordercolor=bg,
    )

    style.configure(
        "TNotebook.Tab",
        background=field,
        foreground=fg,
        padding=[12, 5],
    )

    style.map(
        "TNotebook.Tab",
        background=[("selected", active)],
        foreground=[("selected", "#ffffff")],
    )

    style.configure(
        "Treeview",
        background=field,
        foreground=fg,
        fieldbackground=field,
        rowheight=28,
        bordercolor=bg,
    )

    style.configure(
        "Treeview.Heading",
        background="#26272b",
        foreground=fg,
        padding=5,
    )

    style.map(
        "Treeview",
        background=[("selected", "#3d4045")],
        foreground=[("selected", "#ffffff")],
    )


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1280x820")

        self.populated = set()
        self.priv_prefix = self.detect_priv_prefix()
        self.last_copy_update = 0.0
        self.last_opened_path = ""

        self.mountpoint_var = tk.StringVar(value=default_mountpoint())
        self.copy_status_var = tk.StringVar(value="Ready")

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_drives = ttk.Frame(self.nb)
        self.tab_files = ttk.Frame(self.nb)
        self.tab_info = ttk.Frame(self.nb)
        self.tab_log = ttk.Frame(self.nb)

        self.nb.add(self.tab_drives, text="Partitions && Fixes")
        self.nb.add(self.tab_files, text="Files")
        self.nb.add(self.tab_info, text="Information")
        self.nb.add(self.tab_log, text="Log")

        self.build_drives_tab()
        self.build_files_tab()
        self.build_info_tab()
        self.build_log_tab()

        self.nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.log(f"{APP_NAME} {APP_VERSION}")
        self.log("Default mount point: ~/WindowsPartitionMount (can be changed)")

        if self.priv_prefix is None:
            self.log("WARNING: Not root and no pkexec/sudo helper found.")
            self.log("Privileged mount/umount/ntfsfix actions will fail.")
        elif self.priv_prefix:
            self.log(f"Privileged commands will use: {self.priv_prefix[0]}")
        else:
            self.log("Running as root.")

        self.refresh_drives()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def build_drives_tab(self):
        # Mount point selector
        mp_frame = ttk.Frame(self.tab_drives)
        mp_frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(mp_frame, text="Mount point:").pack(side="left")

        ttk.Entry(
            mp_frame,
            textvariable=self.mountpoint_var,
        ).pack(side="left", fill="x", expand=True, padx=8)

        create_button(
            mp_frame,
            "Remove empty mount folder",
            self.action_remove_mount_folder,
            "secondary",
        ).pack(side="left")

        ttk.Label(
            self.tab_drives,
            text=(
                "The mount point is NOT a copy. It is a live view of the Windows partition. "
                "Use the Files tab copy button if you want real copies inside Ubuntu."
            ),
        ).pack(fill="x", padx=8)

        # Drive list
        tree_frame = ttk.Frame(self.tab_drives)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("device", "fs", "label", "size", "uuid", "mounted")
        self.drive_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
        )

        headings = [
            ("device", "Device", 170),
            ("fs", "Filesystem", 110),
            ("label", "Label", 180),
            ("size", "Size", 90),
            ("uuid", "UUID", 280),
            ("mounted", "Mounted at", 220),
        ]

        for col, text, width in headings:
            self.drive_tree.heading(col, text=text)
            self.drive_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.drive_tree.yview)
        self.drive_tree.configure(yscrollcommand=vsb.set)

        self.drive_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btns = ttk.Frame(self.tab_drives)
        btns.pack(fill="x", padx=8, pady=8)

        for i in range(4):
            btns.grid_columnconfigure(i, weight=1)

        buttons = [
            ("Refresh", self.action_refresh, "secondary"),
            ("UDisks read-only", self.action_udisks, "info"),
            ("Auto safe methods", self.action_auto, "primary"),
            ("Mount RO ntfs-3g", lambda: self.action_ro("ro_ntfs3g"), "info"),
            ("Mount RO ntfs3", lambda: self.action_ro("ro_ntfs3"), "info"),
            ("ntfsfix -d then RO", self.action_ntfsfix, "warning"),
            ("Mount RW clean only", self.action_rw, "warning"),
            ("Remove hibernation file", self.action_hiber, "danger"),
            ("Unmount", self.action_umount, "secondary"),
            ("Open Files tab", self.action_open_files_tab, "secondary"),
        ]

        for idx, (text, command, style) in enumerate(buttons):
            create_button(btns, text, command, style).grid(
                row=idx // 4,
                column=idx % 4,
                padx=4,
                pady=4,
                sticky="ew",
            )

        self.status_var = tk.StringVar(value="Select a Windows partition")
        ttk.Label(self.tab_drives, textvariable=self.status_var).pack(
            fill="x", padx=8, pady=4
        )

    def build_files_tab(self):
        self.path_var = tk.StringVar()

        top = ttk.Frame(self.tab_files)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Current path:").pack(side="left")

        ttk.Entry(
            top,
            textvariable=self.path_var,
            state="readonly",
        ).pack(side="left", fill="x", expand=True, padx=8)

        toolbar = ttk.Frame(self.tab_files)
        toolbar.pack(fill="x", padx=8, pady=4)

        create_button(
            toolbar,
            "Refresh files",
            self.action_refresh_files,
            "secondary",
        ).pack(side="left", padx=4)

        create_button(
            toolbar,
            "Open selected",
            self.action_open_selected,
            "info",
        ).pack(side="left", padx=4)

        create_button(
            toolbar,
            "Copy selected to Ubuntu folder...",
            self.action_copy_selected,
            "success",
        ).pack(side="left", padx=4)

        ttk.Label(toolbar, textvariable=self.copy_status_var).pack(
            side="left", padx=12
        )

        tree_frame = ttk.Frame(self.tab_files)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.file_tree = ttk.Treeview(
            tree_frame,
            columns=("path", "type", "size"),
            show="tree headings",
            selectmode="extended",
        )

        self.file_tree.heading("#0", text="Name")
        self.file_tree.heading("path", text="")
        self.file_tree.heading("type", text="Type")
        self.file_tree.heading("size", text="Size")

        self.file_tree.column("#0", width=520, anchor="w")
        self.file_tree.column("path", width=0, stretch=False)
        self.file_tree.column("type", width=90, anchor="w")
        self.file_tree.column("size", width=110, anchor="e")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)

        self.file_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.file_tree.tag_configure("dir", foreground="#8ab4f8")
        self.file_tree.tag_configure("file", foreground="#e8eaed")
        self.file_tree.tag_configure("placeholder", foreground="#8d9095")

        self.file_tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.file_tree.bind("<Double-1>", self.on_tree_double)

    def build_info_tab(self):
        frame = ttk.Frame(self.tab_info)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        text = tk.Text(
            frame,
            wrap="word",
            padx=14,
            pady=14,
            relief="flat",
            bg="#101114",
            fg="#e8eaed",
            insertbackground="#e8eaed",
        )

        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        text.tag_configure("h1", font=("TkDefaultFont", 15, "bold"), foreground="#8ab4f8")
        text.tag_configure("h2", font=("TkDefaultFont", 12, "bold"), foreground="#81c995")
        text.tag_configure("body", foreground="#e8eaed")
        text.tag_configure("warn", foreground="#f28b82")
        text.tag_configure("good", foreground="#81c995")
        text.tag_configure("mono", font=("Monospace", 10), foreground="#fdd663")

        content = [
            ("h1", f"{APP_NAME} - Information\n"),
            ("body", "\n"),

            ("h2", "1. Mounting is NOT copying\n"),
            ("body",
             "When a Windows partition is mounted, the mount folder only shows the files "
             "that are stored on the Windows partition.\n\n"
             "Example mount folder:\n"),
            ("mono", "~/WindowsPartitionMount\n"),
            ("body",
             "\nThis folder is a live view. The files are not copied into Ubuntu unless "
             "you explicitly copy them using the copy button in the Files tab.\n\n"),

            ("h2", "2. Can I delete files from the mounted drive?\n"),
            ("body",
             "If the partition is mounted read-only, deletion is blocked.\n\n"
             "If the partition is mounted read/write and you delete files, you are deleting "
             "real files from the Windows partition.\n\n"),
            ("warn",
             "Do not delete Windows files unless you fully understand the result.\n\n"),

            ("h2", "3. If I copied files to Ubuntu, can I delete them?\n"),
            ("good",
             "Yes. If you used 'Copy selected to Ubuntu folder...', those copies are normal "
             "Ubuntu files. You can delete them normally from your file manager.\n\n"),

            ("h2", "4. Why does Linux show hibernation errors?\n"),
            ("body",
             "Windows Fast Startup and hibernation leave the NTFS partition in a suspended state. "
             "Linux refuses read/write access to avoid corruption.\n\n"),

            ("h2", "5. Safe options\n"),
            ("good",
             "- UDisks read-only\n"
             "- Mount read-only with ntfs-3g\n"
             "- Mount read-only with ntfs3\n"
             "- Copy files to Ubuntu\n\n"),

            ("h2", "6. Medium-risk option\n"),
            ("body",
             "ntfsfix -d can clear some dirty flags. It is not a full Windows chkdsk repair.\n\n"),

            ("h2", "7. Dangerous option\n"),
            ("warn",
             "remove_hiberfile deletes/removes the Windows hibernation state. "
             "This can corrupt Windows session state or filesystem consistency. "
             "Use only as a last resort.\n\n"),

            ("h2", "8. Permanent fix from Windows\n"),
            ("body", "Boot into Windows, then:\n\n"),
            ("mono",
             "Control Panel\n"
             "  -> Hardware and Sound\n"
             "  -> Power Options\n"
             "  -> Choose what the power buttons do\n"
             "  -> Change settings that are currently unavailable\n"
             "  -> Disable Fast Startup\n\n"),
            ("mono",
             "PowerShell admin:\n"
             "powercfg /h off\n"
             "shutdown /s /t 0\n\n"),

            ("h2", "9. BitLocker\n"),
            ("warn",
             "If the partition is BitLocker encrypted, normal NTFS mounting will not work. "
             "You need Windows or dislocker with the recovery key.\n\n"),

            ("h2", "10. Recommended workflow\n"),
            ("good",
             "1. Try UDisks read-only.\n"
             "2. Try ntfs-3g or ntfs3 read-only.\n"
             "3. Copy needed files to Ubuntu.\n"
             "4. Boot Windows and disable Fast Startup/hibernation.\n"
             "5. Return to Linux and mount again if read/write access is needed.\n"),
        ]

        for tag, chunk in content:
            text.insert("end", chunk, tag)

        text.configure(state="disabled")

    def build_log_tab(self):
        self.log_text = scrolledtext.ScrolledText(
            self.tab_log,
            wrap="word",
            bg="#101114",
            fg="#d2d5da",
            insertbackground="#d2d5da",
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------
    # Basic helpers
    # ------------------------------------------------------------------

    def detect_priv_prefix(self):
        try:
            if os.geteuid() == 0:
                return []
        except AttributeError:
            pass

        if shutil.which("pkexec"):
            return ["pkexec"]

        if shutil.which("sudo"):
            return ["sudo"]

        return None

    def start_thread(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    def log(self, msg):
        self.root.after(0, self._log, str(msg))

    def _log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def set_status(self, msg):
        self.root.after(0, self.status_var.set, msg)

    def set_copy_status(self, msg):
        self.root.after(0, self.copy_status_var.set, msg)

    def run_cmd(self, cmd, privileged=True):
        if privileged:
            if self.priv_prefix is None:
                self.log("ERROR: No privilege helper found and not running as root.")
                return 127, "", "No privilege helper"

            full = self.priv_prefix + cmd
        else:
            full = cmd

        self.log("$ " + cmd_str(full))

        try:
            p = subprocess.run(full, capture_output=True, text=True)
            out = p.stdout.strip()
            err = p.stderr.strip()

            if out:
                self.log(out)
            if err:
                self.log(err)

            return p.returncode, out, err

        except Exception as e:
            self.log(f"Command failed: {e}")
            return 1, "", str(e)

    def get_mountpoint(self):
        mp = self.mountpoint_var.get().strip()
        if not mp:
            mp = default_mountpoint()

        return os.path.abspath(os.path.expanduser(mp))

    def find_mountpoint(self, dev):
        try:
            real = os.path.realpath(dev)
        except Exception:
            real = dev

        if shutil.which("findmnt"):
            p = subprocess.run(
                ["findmnt", "-no", "TARGET", real],
                capture_output=True,
                text=True,
            )

            if p.returncode == 0 and p.stdout.strip():
                return p.stdout.strip().splitlines()[0]

        # Fallback: parse /proc/mounts
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        src = parts[0]
                        target = parts[1]

                        target = (
                            target.replace("\\040", " ")
                            .replace("\\011", "\t")
                            .replace("\\012", "\n")
                            .replace("\\134", "\\")
                        )

                        try:
                            if os.path.realpath(src) == real:
                                return target
                        except Exception:
                            if src == dev:
                                return target

        except Exception:
            pass

        return None

    def source_at_mountpoint(self, mp):
        if not shutil.which("findmnt"):
            return None

        p = subprocess.run(
            ["findmnt", "-no", "SOURCE", mp],
            capture_output=True,
            text=True,
        )

        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip().splitlines()[0]

        return None

    def ensure_mountpoint_dir(self, mp):
        try:
            os.makedirs(mp, exist_ok=True)
            return True
        except PermissionError:
            rc, _, _ = self.run_cmd(["mkdir", "-p", mp])
            return rc == 0
        except Exception as e:
            self.log(f"Cannot create mountpoint: {e}")
            return False

    def confirm_mountpoint_usable(self):
        mp = self.get_mountpoint()

        # If something is already mounted there, do not warn about contents.
        if self.source_at_mountpoint(mp):
            return True

        if os.path.isdir(mp):
            try:
                if os.listdir(mp):
                    return messagebox.askyesno(
                        "Mount folder not empty",
                        f"{mp} already contains files.\n\n"
                        "Mounting will temporarily hide those files while the partition is mounted.\n\n"
                        "Continue?",
                    )
            except PermissionError:
                pass

        return True

    def is_subpath(self, child, parent):
        try:
            child = os.path.realpath(child)
            parent = os.path.realpath(parent)

            return child == parent or child.startswith(parent + os.sep)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Files tab cleanup after unmount
    # ------------------------------------------------------------------

    def clear_files_tab(self, reason=""):
        self.populated.clear()
        self.last_opened_path = ""
        self.file_tree.delete(*self.file_tree.get_children())
        self.path_var.set("")
        self.set_copy_status("Ready")

        if reason:
            self.log(reason)

    def current_files_path_is_stale(self):
        current = self.path_var.get().strip()

        if not current:
            return False

        if not os.path.isdir(current):
            return True

        try:
            real_current = os.path.realpath(current)

            # If the file browser was showing a mountpoint and it is no longer mounted, clear it.
            if self.last_opened_path and shutil.which("findmnt"):
                try:
                    if real_current == os.path.realpath(self.last_opened_path):
                        if not self.source_at_mountpoint(self.last_opened_path):
                            return True
                except Exception:
                    pass

            mp = self.get_mountpoint()
            real_mp = os.path.realpath(mp)

            if real_current == real_mp or real_current.startswith(real_mp + os.sep):
                if shutil.which("findmnt") and not self.source_at_mountpoint(real_mp):
                    return True

        except Exception:
            pass

        return False

    def clear_files_if_stale(self):
        if self.current_files_path_is_stale():
            self.clear_files_tab(
                "Files tab cleared because the previous path is no longer available/mounted."
            )

    def clear_files_after_unmount(self, path):
        current = self.path_var.get().strip()

        if not current:
            return

        # If the path is still mounted, do not clear.
        if path and shutil.which("findmnt") and self.source_at_mountpoint(path):
            return

        try:
            real_current = os.path.realpath(current)

            if path:
                real_target = os.path.realpath(path)

                if real_current == real_target or real_current.startswith(real_target + os.sep):
                    self.clear_files_tab("Files tab cleared after unmount.")
                    return

        except Exception:
            pass

        self.clear_files_if_stale()

    def on_tab_changed(self, event=None):
        try:
            current_tab = self.nb.nametowidget(self.nb.select())
            if current_tab == self.tab_files:
                self.clear_files_if_stale()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Device list
    # ------------------------------------------------------------------

    def collect_windows(self, node, out):
        fstype = (node.get("fstype") or "").lower()
        typ = (node.get("type") or "").lower()

        if fstype in WIN_FSTYPES and typ not in ("rom", "loop"):
            out.append(node)

        for child in node.get("children", []) or []:
            self.collect_windows(child, out)

    def refresh_drives(self):
        for item in self.drive_tree.get_children():
            self.drive_tree.delete(item)

        if not shutil.which("lsblk"):
            self.log("ERROR: lsblk not found. Install util-linux.")
            return

        p = subprocess.run(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,FSTYPE,LABEL,SIZE,UUID,MOUNTPOINT,TYPE",
            ],
            capture_output=True,
            text=True,
        )

        if p.returncode != 0:
            self.log("lsblk failed:")
            self.log(p.stderr.strip())
            return

        try:
            data = json.loads(p.stdout)
        except Exception as e:
            self.log(f"Failed to parse lsblk JSON: {e}")
            return

        devices = []
        for dev in data.get("blockdevices", []):
            self.collect_windows(dev, devices)

        devices.sort(key=lambda x: x.get("name", ""))

        for d in devices:
            name = d.get("name", "")
            path = name if name.startswith("/dev/") else f"/dev/{name}"

            mounted = self.find_mountpoint(path) or d.get("mountpoint") or ""

            self.drive_tree.insert(
                "",
                "end",
                values=(
                    path,
                    d.get("fstype", ""),
                    d.get("label", ""),
                    d.get("size", ""),
                    d.get("uuid", ""),
                    mounted,
                ),
            )

        self.set_status(f"{len(devices)} Windows-like partition(s) found")

    def get_selected_device(self, silent=False):
        sel = self.drive_tree.selection()

        if not sel:
            if not silent:
                messagebox.showinfo("No selection", "Select a partition first.")
            return None, None

        vals = self.drive_tree.item(sel[0], "values")
        if not vals:
            return None, None

        return str(vals[0]), str(vals[1]).lower()

    def bitlocker_warning(self):
        messagebox.showwarning(
            "BitLocker detected",
            "This partition appears to be BitLocker encrypted.\n\n"
            "Simple NTFS mounting will not work.\n\n"
            "You need either:\n"
            "1. Unlock it from Windows, or\n"
            "2. Use dislocker with the recovery key/password.\n\n"
            "Example:\n"
            "sudo apt install dislocker\n"
            "sudo dislocker /dev/sdXn -p<RecoveryKey> -- /mnt/dislocker\n"
            "sudo mount -o ro /mnt/dislocker/dislocker-file /mnt/win",
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_refresh(self):
        self.refresh_drives()

    def action_open_files_tab(self):
        self.nb.select(self.tab_files)

    def action_udisks(self):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        self.start_thread(self.udisks_worker, dev)

    def action_auto(self):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        if not self.confirm_mountpoint_usable():
            return

        ok = messagebox.askyesno(
            "Auto safe methods",
            "This will try:\n\n"
            "1. UDisks read-only\n"
            "2. ntfs-3g read-only\n"
            "3. ntfs3 read-only\n"
            "4. ntfsfix -d, then read-only mounts again\n\n"
            "ntfsfix can modify NTFS metadata slightly.\n\n"
            "Continue?",
        )

        if not ok:
            return

        self.start_thread(self.auto_worker, dev)

    def action_ro(self, method):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        if not self.confirm_mountpoint_usable():
            return

        self.start_thread(self.mount_worker, dev, method)

    def action_ntfsfix(self):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        if not self.confirm_mountpoint_usable():
            return

        ok = messagebox.askyesno(
            "ntfsfix",
            "This will run:\n"
            "ntfsfix -d /dev/...\n\n"
            "then attempt read-only mount.\n\n"
            "ntfsfix is not a full Windows chkdsk repair.\n"
            "Continue?",
        )

        if not ok:
            return

        self.start_thread(self.ntfsfix_worker, dev)

    def action_rw(self):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        if not self.confirm_mountpoint_usable():
            return

        ok = messagebox.askyesno(
            "Read-write mount",
            "Read-write mounting is only safe if Windows was fully shut down.\n\n"
            "If Windows is hibernated or Fast Startup is enabled,\n"
            "writing to this partition can corrupt Windows.\n\n"
            "Continue anyway?",
        )

        if not ok:
            return

        self.start_thread(self.rw_worker, dev)

    def action_hiber(self):
        dev, fs = self.get_selected_device()
        if not dev:
            return

        if fs == "bitlocker":
            self.bitlocker_warning()
            return

        if not self.confirm_mountpoint_usable():
            return

        ok = messagebox.askyesno(
            "DANGEROUS",
            "This will mount using:\n"
            "remove_hiberfile\n\n"
            "This deletes/removes the Windows hibernation state.\n"
            "It may cause Windows to lose saved session state and\n"
            "can potentially cause filesystem corruption.\n\n"
            "Use only if you understand the risk.\n\n"
            "Continue?",
        )

        if not ok:
            return

        self.start_thread(self.mount_worker, dev, "remove_hiberfile")

    def action_umount(self):
        dev, _ = self.get_selected_device(silent=True)

        if not dev:
            src = self.source_at_mountpoint(self.get_mountpoint())
            if src:
                dev = src

        if not dev:
            messagebox.showinfo(
                "Unmount",
                "Select a partition or mount something first.",
            )
            return

        self.start_thread(self.umount_worker, dev)

    def action_remove_mount_folder(self):
        mp = self.get_mountpoint()

        if self.source_at_mountpoint(mp):
            messagebox.showwarning(
                "Mount folder in use",
                f"{mp} is currently a mounted filesystem.\n\n"
                "Unmount first before removing the folder.",
            )
            return

        if not os.path.isdir(mp):
            messagebox.showinfo(
                "Remove mount folder",
                f"{mp} does not exist.",
            )
            return

        try:
            if os.listdir(mp):
                messagebox.showwarning(
                    "Folder not empty",
                    f"{mp} is not empty.\n\n"
                    "Only empty mount folders should be removed automatically.\n\n"
                    "If you are sure the remaining files are not important, "
                    "delete them manually from your file manager.",
                )
                return
        except PermissionError:
            pass
        except FileNotFoundError:
            messagebox.showinfo(
                "Remove mount folder",
                f"{mp} does not exist.",
            )
            return

        ok = messagebox.askyesno(
            "Remove empty mount folder",
            f"Remove empty folder?\n\n{mp}",
        )

        if not ok:
            return

        try:
            os.rmdir(mp)
            messagebox.showinfo("Removed", f"Removed:\n{mp}")
            self.clear_files_after_unmount(mp)
        except PermissionError:
            self.start_thread(self.remove_mount_folder_worker, mp)
        except OSError as e:
            messagebox.showwarning("Could not remove folder", str(e))

    def remove_mount_folder_worker(self, mp):
        self.run_cmd(["rmdir", mp])
        self.root.after(0, self.clear_files_after_unmount, mp)
        self.root.after(0, self.refresh_drives)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def udisks_worker(self, dev):
        self.set_status("Trying UDisks read-only...")

        if self.try_udisks_ro(dev):
            self.set_status("Mounted via UDisks")
        else:
            self.set_status("UDisks mount failed")

    def auto_worker(self, dev):
        self.set_status("Trying safe methods...")

        mp = self.find_mountpoint(dev)
        if mp:
            self.log(f"{dev} already mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            self.set_status(f"Already mounted at {mp}")
            return

        if self.try_udisks_ro(dev):
            self.set_status("Mounted via UDisks")
            return

        if not self.prepare_mountpoint(dev):
            self.set_status("Mountpoint preparation failed")
            return

        for method in ["ro_ntfs3g", "ro_ntfs3"]:
            if self.try_mount(dev, method):
                self.set_status("Mounted successfully")
                return

        self.log("Read-only mount failed. Trying ntfsfix -d ...")
        self.run_cmd(["ntfsfix", "-d", dev])

        for method in ["ro_ntfs3g", "ro_ntfs3"]:
            if self.try_mount(dev, method):
                self.set_status("Mounted after ntfsfix")
                return

        self.log("Automatic safe methods failed.")
        self.log("")
        self.log("Likely fixes:")
        self.log("1. Boot Windows.")
        self.log("2. Disable Fast Startup.")
        self.log("3. Run: powercfg /h off")
        self.log("4. Shut down Windows fully: shutdown /s /t 0")
        self.log("")
        self.log("Or use the dangerous remove_hiberfile option only if you accept the risk.")

        self.set_status("Auto methods failed")

    def mount_worker(self, dev, method):
        self.set_status(f"Trying {method}...")

        mp = self.find_mountpoint(dev)
        if mp:
            self.log(f"{dev} already mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            self.set_status(f"Mounted at {mp}")
            return

        if not self.prepare_mountpoint(dev):
            self.set_status("Mountpoint preparation failed")
            return

        if self.try_mount(dev, method):
            self.set_status("Mounted successfully")
        else:
            self.set_status("Mount failed")

    def ntfsfix_worker(self, dev):
        self.set_status("Running ntfsfix -d...")

        mp = self.find_mountpoint(dev)
        if mp:
            self.log(f"{dev} already mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            self.set_status(f"Mounted at {mp}")
            return

        self.run_cmd(["ntfsfix", "-d", dev])

        if not self.prepare_mountpoint(dev):
            self.set_status("Mountpoint preparation failed")
            return

        if not self.try_mount(dev, "ro_ntfs3g"):
            self.try_mount(dev, "ro_ntfs3")

    def rw_worker(self, dev):
        self.set_status("Trying read-write mount...")

        mp = self.find_mountpoint(dev)
        if mp:
            self.log(f"{dev} already mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            self.set_status(f"Mounted at {mp}")
            return

        if not self.prepare_mountpoint(dev):
            self.set_status("Mountpoint preparation failed")
            return

        if not self.try_mount(dev, "rw_ntfs3g"):
            self.try_mount(dev, "rw_ntfs3")

    def umount_worker(self, dev):
        self.set_status("Unmounting...")

        mp = self.find_mountpoint(dev)
        mp_to_clear = mp or self.get_mountpoint()

        if not mp:
            src = self.source_at_mountpoint(self.get_mountpoint())
            if src:
                try:
                    if os.path.realpath(src) == os.path.realpath(dev):
                        mp = self.get_mountpoint()
                        mp_to_clear = mp
                except Exception:
                    pass

        if not mp:
            self.log(f"{dev} does not appear to be mounted.")
            self.set_status("Not mounted")
            self.root.after(0, self.clear_files_after_unmount, mp_to_clear)
            return

        rc, _, _ = self.run_cmd(["umount", mp])

        if rc != 0:
            self.log("Unmount by mountpoint failed. Trying device path.")
            self.run_cmd(["umount", dev])

        self.set_status("Unmount attempted")
        self.root.after(0, self.refresh_drives)
        self.root.after(0, self.clear_files_after_unmount, mp_to_clear)

    # ------------------------------------------------------------------
    # Mount helpers
    # ------------------------------------------------------------------

    def prepare_mountpoint(self, dev):
        mp = self.get_mountpoint()

        if not self.ensure_mountpoint_dir(mp):
            return False

        src = self.source_at_mountpoint(mp)

        if src:
            try:
                if os.path.realpath(src) != os.path.realpath(dev):
                    self.log(f"{mp} is currently used by {src}. Trying to unmount it first.")
                    self.run_cmd(["umount", mp])
            except Exception:
                pass

        # Warn in log if local files exist in the mountpoint.
        try:
            if os.path.isdir(mp) and os.listdir(mp):
                self.log(f"WARNING: {mp} is not empty. Mounting will hide existing local files temporarily.")
        except Exception:
            pass

        return True

    def try_udisks_ro(self, dev):
        mp = self.find_mountpoint(dev)
        if mp:
            self.log(f"{dev} already mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            return True

        if not shutil.which("udisksctl"):
            self.log("udisksctl not found. Skipping UDisks method.")
            return False

        self.log("Trying UDisks read-only mount...")

        rc, _, err = self.run_cmd(
            ["udisksctl", "mount", "-b", dev, "-o", "ro"],
            privileged=False,
        )

        if rc == 0:
            mp = self.find_mountpoint(dev)
            if mp:
                self.log(f"SUCCESS: {dev} mounted via UDisks at {mp}")
                self.root.after(0, self.open_path, mp)
                self.root.after(0, self.refresh_drives)
                return True

        self.explain_mount_error(err, "udisks-ro")
        return False

    def build_mount_cmd(self, dev, method):
        mp = self.get_mountpoint()

        uid = os.getuid() if hasattr(os, "getuid") else 0
        gid = os.getgid() if hasattr(os, "getgid") else 0

        try:
            uid = int(os.environ.get("SUDO_UID", uid))
            gid = int(os.environ.get("SUDO_GID", gid))
        except Exception:
            pass

        if method == "ro_ntfs3g":
            opts = f"ro,uid={uid},gid={gid}"
            fstype = "ntfs-3g"

        elif method == "ro_ntfs3":
            opts = f"ro,uid={uid},gid={gid},umask=022"
            fstype = "ntfs3"

        elif method == "rw_ntfs3g":
            opts = f"rw,uid={uid},gid={gid}"
            fstype = "ntfs-3g"

        elif method == "rw_ntfs3":
            opts = f"rw,noatime,uid={uid},gid={gid},umask=022"
            fstype = "ntfs3"

        elif method == "remove_hiberfile":
            opts = f"remove_hiberfile,uid={uid},gid={gid}"
            fstype = "ntfs-3g"

        else:
            raise ValueError(f"Unknown method: {method}")

        return ["mount", "-t", fstype, "-o", opts, dev, mp]

    def try_mount(self, dev, method):
        cmd = self.build_mount_cmd(dev, method)
        rc, _, err = self.run_cmd(cmd)

        if rc == 0:
            mp = self.find_mountpoint(dev) or self.get_mountpoint()
            self.log(f"SUCCESS: {dev} mounted at {mp}")
            self.root.after(0, self.open_path, mp)
            self.root.after(0, self.refresh_drives)
            return True

        self.log(f"FAILED: {method}")
        self.explain_mount_error(err, method)
        return False

    def explain_mount_error(self, err, method):
        if not err:
            return

        e = err.lower()

        if any(x in e for x in [
            "hibernated",
            "unsafe state",
            "metadata kept",
            "windows is hibernated",
        ]):
            self.log("")
            self.log("EXPLANATION:")
            self.log("Windows is hibernated or was not fully shut down.")
            self.log("This is usually caused by Fast Startup.")
            self.log("")
            self.log("SAFE FIX:")
            self.log("1. Boot Windows.")
            self.log("2. Disable Fast Startup.")
            self.log("3. Run: powercfg /h off")
            self.log("4. Run: shutdown /s /t 0")
            self.log("")
            self.log("Linux last resort:")
            self.log("remove_hiberfile, but this is dangerous.")
            self.log("")

        elif "bitlocker" in e:
            self.log("")
            self.log("EXPLANATION:")
            self.log("This partition appears to be BitLocker encrypted.")
            self.log("Use Windows or dislocker with the recovery key.")
            self.log("")

        elif "unknown filesystem type" in e:
            self.log("")
            self.log("EXPLANATION:")
            self.log("The kernel or system does not support the requested NTFS driver.")
            self.log("Install ntfs-3g or use a newer kernel with ntfs3 support.")
            self.log("")

        elif "permission denied" in e:
            self.log("")
            self.log("EXPLANATION:")
            self.log("Permission denied. Privilege escalation failed or was cancelled.")
            self.log("")

        elif "device or resource busy" in e:
            self.log("")
            self.log("EXPLANATION:")
            self.log("The device or mountpoint is busy.")
            self.log("Close file managers/terminals using it, then unmount and retry.")
            self.log("")

        elif "no such file or directory" in e:
            self.log("")
            self.log("EXPLANATION:")
            self.log("A required file/device/directory was not found.")
            self.log("Check the mount point and partition path.")
            self.log("")

    # ------------------------------------------------------------------
    # File browser
    # ------------------------------------------------------------------

    def open_path(self, path):
        if not os.path.isdir(path):
            self.log(f"Path is not a directory: {path}")
            return

        self.path_var.set(path)
        self.last_opened_path = os.path.abspath(path)
        self.populated.clear()

        self.file_tree.delete(*self.file_tree.get_children())

        label = os.path.basename(path.rstrip("/")) or "/"

        item = self.file_tree.insert(
            "",
            "end",
            text=f"{dir_icon()} {label}",
            values=(path, "dir", ""),
            tags=("dir",),
            open=True,
        )

        self.populate_dir(item)
        self.nb.select(self.tab_files)

    def populate_dir(self, item):
        path = self.file_tree.set(item, "path")

        if path in self.populated:
            return

        self.populated.add(path)

        for old in self.file_tree.get_children(item):
            self.file_tree.delete(old)

        try:
            entries = list(os.scandir(path))
            entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        except Exception as e:
            self.log(f"Cannot list {path}: {e}")
            return

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    child = self.file_tree.insert(
                        item,
                        "end",
                        text=f"{dir_icon()} {entry.name}",
                        values=(entry.path, "dir", ""),
                        tags=("dir",),
                    )

                    self.file_tree.insert(
                        child,
                        "end",
                        text="…",
                        values=("", "placeholder", ""),
                        tags=("placeholder",),
                    )
                else:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        size = human_size(st.st_size)
                    except Exception:
                        size = ""

                    self.file_tree.insert(
                        item,
                        "end",
                        text=f"{file_icon(entry.name)} {entry.name}",
                        values=(entry.path, "file", size),
                        tags=("file",),
                    )

            except Exception as e:
                self.log(f"Skipping entry: {e}")

    def on_tree_open(self, event):
        item = self.file_tree.focus()
        if not item:
            return

        typ = self.file_tree.set(item, "type")
        if typ != "dir":
            return

        self.populate_dir(item)

    def on_tree_double(self, event):
        try:
            item = self.file_tree.identify_row(event.y)
        except AttributeError:
            item = self.file_tree.identify("row", event.x, event.y)

        if not item:
            return

        typ = self.file_tree.set(item, "type")
        path = self.file_tree.set(item, "path")

        if typ == "dir":
            self.populate_dir(item)
            self.file_tree.item(item, open=True)

        elif typ == "file":
            try:
                subprocess.Popen(["xdg-open", path])
            except Exception as e:
                messagebox.showerror("Open failed", f"Could not open file:\n{e}")

    def action_refresh_files(self):
        self.clear_files_if_stale()

        path = self.path_var.get().strip()
        if path and os.path.isdir(path):
            self.open_path(path)
        else:
            messagebox.showinfo("Refresh", "No mounted path is currently open.")

    def action_open_selected(self):
        sel = self.file_tree.selection()

        if not sel:
            messagebox.showinfo("Open selected", "Select a file or folder first.")
            return

        item = sel[0]
        typ = self.file_tree.set(item, "type")
        path = self.file_tree.set(item, "path")

        if typ == "dir":
            self.populate_dir(item)
            self.file_tree.item(item, open=True)

        elif typ == "file":
            try:
                subprocess.Popen(["xdg-open", path])
            except Exception as e:
                messagebox.showerror("Open failed", f"Could not open file:\n{e}")

    def get_selected_file_paths(self):
        paths = []

        for item in self.file_tree.selection():
            typ = self.file_tree.set(item, "type")

            if typ not in ("file", "dir"):
                continue

            path = self.file_tree.set(item, "path")
            if path:
                paths.append(path)

        return paths

    def action_copy_selected(self):
        paths = self.get_selected_file_paths()

        if not paths:
            messagebox.showinfo(
                "Copy selected",
                "Select one or more files/folders in the Files tab first.",
            )
            return

        dest = filedialog.askdirectory(
            title="Choose Ubuntu destination folder",
        )

        if not dest:
            return

        dest = os.path.abspath(dest)

        current_root = self.path_var.get().strip()

        if current_root and self.is_subpath(dest, current_root):
            messagebox.showwarning(
                "Invalid destination",
                "Do not copy into the same mounted Windows partition.\n\n"
                "Choose a normal Ubuntu folder such as Home, Documents, Downloads, etc.",
            )
            return

        for src in paths:
            if self.is_subpath(dest, src):
                messagebox.showwarning(
                    "Invalid destination",
                    f"Destination is inside the selected source:\n\n{src}\n\n"
                    "Choose another destination folder.",
                )
                return

        ok = messagebox.askyesno(
            "Copy",
            f"Copy {len(paths)} selected item(s) to:\n\n{dest}\n\n"
            "Existing files with the same name may be overwritten/merged.\n\n"
            "Continue?",
        )

        if not ok:
            return

        self.start_thread(self.copy_worker, paths, dest)

    def copy_worker(self, sources, dest):
        total = len(sources)

        try:
            os.makedirs(dest, exist_ok=True)
        except Exception as e:
            self.log(f"Cannot create destination folder: {e}")
            self.set_copy_status("Copy failed")
            return

        for idx, src in enumerate(sources, 1):
            name = os.path.basename(src.rstrip("/")) or "root"
            target = os.path.join(dest, name)

            self.set_copy_status(f"Item {idx}/{total}: {name}")

            try:
                if os.path.isdir(src):
                    shutil.copytree(
                        src,
                        target,
                        copy_function=self.copy_file_progress,
                        dirs_exist_ok=True,
                    )
                else:
                    self.copy_file_progress(src, target)

            except Exception as e:
                self.log(f"Copy error: {e}")

        self.set_copy_status("Copy completed")
        self.log(f"Copied {total} item(s) to {dest}")

        self.root.after(
            0,
            lambda: messagebox.showinfo(
                "Copy completed",
                f"Copied {total} item(s) to:\n\n{dest}",
            ),
        )

    def copy_file_progress(self, src, dst):
        now = time.time()

        if now - self.last_copy_update > 0.12:
            self.set_copy_status(f"Copying: {os.path.basename(src)}")
            self.last_copy_update = now

        try:
            shutil.copy2(src, dst)
        except Exception:
            # If metadata preservation fails, fall back to plain file copy.
            shutil.copyfile(src, dst)

        return dst


def main():
    if HAS_BOOTSTRAP:
        root = ttk.Window(themename="darkly")
    else:
        root = tk.Tk()
        apply_fallback_dark(root)

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()