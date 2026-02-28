# File: App/ui_subjects_dialogs.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Dialogs for SubjectWindow.

Provides the Categories… modal picker.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .utils import normalize_token


# This shows a modal dialog of categories and inserts the chosen category into SubjectWindow. (Start)
def show_categories_dialog(win) -> None:
    try:
        cats = win.db.list_categories(min_words=1)
    except Exception:
        cats = []
    # end try/except

    if not cats:
        messagebox.showerror("No Categories", "No categories exist yet in the database.", parent=win.root)
        return
    # end if

    # Do NOT include Surprise Me! here; this dialog is only real DB categories. (Start)
    cats_sorted = sorted(cats, key=lambda s: normalize_token(s).casefold())
    # end categories sort

    dlg = tk.Toplevel(win.root)
    dlg.title("Categories")
    dlg.transient(win.root)
    dlg.grab_set()

    tk.Label(dlg, text="Select a category:", font=("Helvetica", 12, "bold")).pack(
        anchor="w", padx=10, pady=(10, 6)
    )

    listbox = tk.Listbox(dlg, width=44, height=18)
    listbox.pack(padx=10, pady=(0, 8), fill="both", expand=True)

    for c in cats_sorted:
        listbox.insert(tk.END, c)
    # end for

    btns = tk.Frame(dlg)
    btns.pack(padx=10, pady=(0, 10), anchor="e")

    # This inserts the selected category into the first empty entry row. (Start)
    def do_add() -> None:
        sel = listbox.curselection()
        if not sel:
            return
        # end if
        cat = cats_sorted[int(sel[0])]
        try:
            dlg.destroy()
        except tk.TclError:
            pass
        # end try/except
        win.fill_and_focus(cat)
    # end def do_add  # do_add

    tk.Button(btns, text="Add", width=10, command=do_add).pack(side="right", padx=(8, 0))
    tk.Button(btns, text="Close", width=10, command=dlg.destroy).pack(side="right")

    listbox.bind("<Double-Button-1>", lambda _e: do_add())

    # Grab focus so it doesn't hide under other windows. (Start)
    try:
        dlg.lift()
        dlg.attributes("-topmost", True)
        dlg.update_idletasks()
        listbox.focus_force()
        dlg.attributes("-topmost", False)
    except tk.TclError:
        pass
    # end try/except
# end def show_categories_dialog  # show_categories_dialog
