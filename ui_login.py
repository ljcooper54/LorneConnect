# File: App/ui_login.py | Created/Modified: 2026-02-25
# Copyright 2025 H2so4 Consulting LLC
"""Login UI.

Shows a simple name entry dialog and guarantees that the Entry grabs keyboard focus on launch
(especially important on macOS where focus can be lost at startup).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .utils import normalize_token


# This LoginWindow renders the login screen and returns the user name via callback. (Start)
class LoginWindow:
    """Login screen with a focused Entry widget."""

    # This initializes the login UI and schedules initial focus. (Start)
    def __init__(self, root: tk.Tk, callback):
        self.root = root
        self.callback = callback

        self.frame = tk.Frame(root)
        self.frame.pack(padx=22, pady=22)

        title = tk.Label(self.frame, text="Enter your name", font=("Helvetica", 16, "bold"))
        title.pack(pady=(0, 12))

        self.entry = tk.Entry(self.frame, width=28, font=("Helvetica", 14))
        self.entry.pack(pady=(0, 10))
        self.entry.bind("<Return>", lambda _e: self.submit())

        btn = tk.Button(self.frame, text="Continue", width=12, command=self.submit)
        btn.pack()

        hint = tk.Label(self.frame, text="(Press Return to continue)", font=("Helvetica", 11))
        hint.pack(pady=(10, 0))

        # Force keyboard focus into the Entry after Tk maps the widgets. (Start)
        self.root.after_idle(self._force_initial_focus)
        # end focus scheduling
    # end def __init__  # __init__

    # This forces focus into the Entry and raises the window (macOS-friendly). (Start)
    def _force_initial_focus(self) -> None:
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.update_idletasks()

            self.entry.focus_force()
            self.entry.selection_range(0, tk.END)
            self.entry.icursor(tk.END)

            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass
        # end try/except
    # end def _force_initial_focus  # _force_initial_focus

    # This validates input and calls the callback with the normalized user name. (Start)
    def submit(self) -> None:
        name_raw = self.entry.get()
        name = normalize_token(name_raw)

        if not name:
            messagebox.showerror("Name Required", "Please enter your name.", parent=self.root)
            self._force_initial_focus()
            return
        # end if

        self.callback(name)
    # end def submit  # submit

# end class LoginWindow  # LoginWindow
