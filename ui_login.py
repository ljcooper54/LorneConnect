# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Login UI."""

import tkinter as tk
from tkinter import messagebox

class LoginWindow:
    """Login window (Enter == Continue)."""

    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self.frame = tk.Frame(root)
        self.frame.pack(padx=20, pady=20)

        tk.Label(self.frame, text="Enter your name").pack()
        self.entry = tk.Entry(self.frame, width=30)
        self.entry.pack()
        self.entry.focus_set()
        self.entry.bind("<Return>", self._on_return)

        tk.Button(self.frame, text="Continue", command=self.submit).pack(pady=10)

    def _on_return(self, _event):
        self.submit()

    def submit(self):
        name = normalize_token(self.entry.get())
        if not name:
            return
        self.frame.destroy()
        self.callback(name)

# end class LoginWindow
