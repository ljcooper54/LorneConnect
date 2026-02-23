# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Subject chooser UI."""

import tkinter as tk
from tkinter import messagebox
import random

from .db import DB

class SubjectWindow:
    """Subject picker with Surprise Me."""

    def __init__(self, root, user, db: DB, callback):
        self.root = root
        self.user = user
        self.db = db
        self.callback = callback

        self.frame = tk.Frame(root)
        self.frame.pack(padx=20, pady=20)

        played, solved = self.db.get_stats(user)
        tk.Label(self.frame, text=f"{self.user}, you\'ve solved {solved} puzzles!\nEnter up to 8 favorite subjects").pack()

        self.entries = []
        self.defaults = self.db.get_recent_subjects(user, limit=8)

        for i in range(8):
            e = tk.Entry(self.frame, width=40)
            e.pack(pady=2)
            if i < len(self.defaults):
                e.insert(0, self.defaults[i])
            self.entries.append(e)

        self.entries[0].focus_set()

        btn_row = tk.Frame(self.frame)
        btn_row.pack(pady=10)

        self.play_btn = tk.Button(btn_row, text="Play!", command=self.submit)
        self.play_btn.pack(side=tk.LEFT, padx=6)

        self.surprise_btn = tk.Button(btn_row, text="Surprise Me!", command=self.surprise_me)
        self.surprise_btn.pack(side=tk.LEFT, padx=6)

    def surprise_me(self):
        target = None
        for i, e in enumerate(self.entries):
            if not normalize_token(e.get()):
                target = i
                break
        if target is None:
            target = len(self.entries) - 1
        self.entries[target].delete(0, tk.END)
        self.entries[target].insert(0, "Surprise Me!")

    def submit(self):
        raw = [normalize_token(e.get()) for e in self.entries]

        # delete overwritten defaults
        for i, default in enumerate(self.defaults):
            if i >= len(raw):
                break
            current = raw[i]
            if default and current and current != default:
                self.db.delete_subject(self.user, default)

        subjects = [s for s in raw if s]

        prior = self.db.get_subjects(self.user)
        candidates = [p for p in prior if p not in subjects]
        random.shuffle(candidates)
        while len(subjects) < 8 and candidates:
            subjects.append(candidates.pop())

        if not subjects:
            messagebox.showerror("Error", "Please enter at least one subject.")
            return

        self.db.add_subjects(self.user, subjects)
        self.callback(subjects, self)

    def disable(self):
        self.play_btn.config(state=tk.DISABLED)
        self.surprise_btn.config(state=tk.DISABLED)
        for e in self.entries:
            e.config(state=tk.DISABLED)

    def enable(self):
        self.play_btn.config(state=tk.NORMAL)
        self.surprise_btn.config(state=tk.NORMAL)
        for e in self.entries:
            e.config(state=tk.NORMAL)

    def destroy(self):
        self.frame.destroy()

# end class SubjectWindow
