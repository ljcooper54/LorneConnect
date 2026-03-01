# File: App/app_controller.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""App controller.

Fixes:
- Cancel from Choose Categories exits the app.
- Uses CategorySeeder(db) aligned signature.
- Shows generation spinner with Cancel.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from dotenv import load_dotenv

from .category_seed import CategorySeeder, CategoryTooNarrowError
from .db import DB
from .generator import PuzzleGenerator
from .spinner import GeneratingWindow
from .ui_game import PuzzleGame
from .ui_login import LoginWindow
from .ui_subjects import SubjectWindow
from .utils import normalize_token


# This App class coordinates tkinter UI flow and background puzzle generation. (Start)
class App:
    """Main controller."""

    # This initializes environment, DB, seeder, generator, and shows login. (Start)
    def __init__(self, root: tk.Tk):
        self.root = root

        project_root = Path(__file__).resolve().parent.parent
        load_dotenv(project_root / ".env")

        import os
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not found. Ensure .env exists and is loaded.")
        # end if

        self.db = DB()
        from .debug import debug_log_category_obscurity_csv_excel
        debug_log_category_obscurity_csv_excel(self.db)
        self.seeder = CategorySeeder(self.db)
        self.generator = PuzzleGenerator(self.db)

        self.user: str | None = None
        self._show_login()
    # end def __init__  # __init__

    # This clears any existing frames. (Start)
    def _clear_frames(self) -> None:
        for child in list(self.root.winfo_children()):
            if isinstance(child, tk.Frame):
                child.destroy()
            # end if
        # end for
    # end def _clear_frames  # _clear_frames

    # This shows the login UI. (Start)
    def _show_login(self) -> None:
        self._clear_frames()
        LoginWindow(self.root, self.after_login)
    # end def _show_login  # _show_login

    # This handles login completion. (Start)
    def after_login(self, user: str) -> None:
        self.user = normalize_token(user)
        self.db.ensure_user_stats(self.user or "")
        self._show_subjects()
    # end def after_login  # after_login

    # This shows the category chooser. (Start)
    def _show_subjects(self) -> None:
        self._clear_frames()
        SubjectWindow(self.root, self.user, self.db, self.after_subjects)
    # end def _show_subjects  # _show_subjects

    # This focuses/selects the entry matching category (best effort). (Start)
    def _focus_category_entry(self, subject_window: SubjectWindow, category: str) -> None:
        target_key = normalize_token(category).casefold().replace(" ", "")
        if not target_key:
            return
        # end if
        for e in getattr(subject_window, "entries", []):
            raw = normalize_token(e.get())
            if raw.casefold().replace(" ", "") == target_key:
                try:
                    e.focus_force()
                    e.selection_range(0, tk.END)
                except tk.TclError:
                    pass
                # end try/except
                return
            # end if
        # end for
    # end def _focus_category_entry  # _focus_category_entry

    # This handles category selection completion (or cancel). (Start)
    def after_subjects(self, subjects: list[str], subject_window: SubjectWindow) -> None:
        # Cancel from chooser: exit app. (Start)
        if not subjects:
            try:
                subject_window.destroy()
            except Exception:
                pass
            # end try/except
            self.root.destroy()
            return
        # end if

        subject_window.disable()

        spinner = GeneratingWindow(self.root, title="Generating Puzzle", message="Generating puzzle…")
        spinner.start_dots("Generating puzzle")
        spinner.focus_modal()

        q: queue.Queue = queue.Queue()
        cancelled = {"v": False}

        # This cancels generation and returns to chooser. (Start)
        def on_cancel() -> None:
            cancelled["v"] = True
            try:
                spinner.stop_dots()
            except Exception:
                pass
            # end try/except
            try:
                spinner.destroy()
            except Exception:
                pass
            # end try/except
            subject_window.enable()
        # end def on_cancel  # on_cancel

        tk.Button(spinner.button_frame, text="Cancel", command=on_cancel, width=10).pack()

        # This posts status updates from worker thread. (Start)
        def progress_cb(msg: str) -> None:
            if cancelled["v"]:
                return
            # end if
            q.put(("progress", str(msg)))
        # end def progress_cb  # progress_cb

        user = self.user or ""
        selected_subjects = subjects

        # This seeds required categories then generates DB-only puzzle. (Start)
        def worker() -> None:
            try:
                for s in selected_subjects:
                    if normalize_token(s).casefold().replace(" ", "") == "surpriseme!":
                        continue
                    # end if
                    self.seeder.ensure_category_playable(user=user, category=s, progress_cb=progress_cb)
                # end for

                puzzle = self.generator.generate(user, selected_subjects, recent_n=0)
                # Normalize older generator payloads (rows->groups). (Start)
                if isinstance(puzzle, dict) and "groups" not in puzzle and "rows" in puzzle:
                    puzzle["groups"] = puzzle.get("rows")
                # end normalize

                # Retry a few times if generator returns an incomplete puzzle. (Start)
                attempts_left = 2
                while True:
                    groups = puzzle.get("groups") if isinstance(puzzle, dict) else None
                    ok = (
                        isinstance(groups, list)
                        and len(groups) == 4
                        and all(isinstance(g, dict) and isinstance(g.get("words"), list) and len(g.get("words")) == 4 for g in groups)
                    )
                    if ok:
                        break
                    # end if

                    if attempts_left <= 0:
                        raise RuntimeError(f"Generator returned invalid groups (need 4x4). Got: {repr(puzzle)[:1200]}")
                    # end if

                    attempts_left -= 1
                    puzzle = self.generator.generate(user, selected_subjects, recent_n=0)
                    if isinstance(puzzle, dict) and "groups" not in puzzle and "rows" in puzzle:
                        puzzle["groups"] = puzzle.get("rows")
                    # end if
                # end while
                # end retry
                q.put(("ok", puzzle))
            except CategoryTooNarrowError as e:
                q.put(("too_narrow", e))
            except Exception as e:
                q.put(("err", str(e)))
            # end try/except
        # end def worker  # worker

        threading.Thread(target=worker, daemon=True).start()

        # This polls progress/results and updates UI. (Start)
        def poll() -> None:
            if cancelled["v"]:
                return
            # end if
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                self.root.after(120, poll)
                return
            # end try/except

            if kind == "progress":
                spinner.set_message(payload)
                self.root.after(60, poll)
                return
            # end if

            spinner.stop_dots()
            spinner.destroy()

            if cancelled["v"]:
                subject_window.enable()
                return
            # end if

            if kind == "too_narrow":
                err: CategoryTooNarrowError = payload
                msg = (
                    "Can't think of enough terms for this category. Please choose another.\n\n"
                    f"Category: {err.category}\nUsable words available: {err.usable_count}"
                )
                if err.note:
                    msg += f"\n\nOpenAI note: {err.note}"
                # end if
                messagebox.showerror("Category Too Narrow", msg, parent=self.root)
                subject_window.enable()
                self._focus_category_entry(subject_window, err.category)
                return
            # end if

            if kind == "err":
                messagebox.showerror("Puzzle Generation Failed", str(payload), parent=self.root)
                subject_window.enable()
                return
            # end if

            puzzle = payload
            if not isinstance(puzzle, dict) or "groups" not in puzzle:
                messagebox.showerror("Puzzle Generation Failed", "Generator returned invalid puzzle data.", parent=self.root)
                subject_window.enable()
                return
            # end if

            try:
                self.db.inc_played(user)
            except Exception:
                pass
            # end try/except

            subject_window.destroy()
            self._clear_frames()
            PuzzleGame(self.root, user, self.db, self.generator, puzzle, self.on_done)
        # end def poll  # poll

        poll()
    # end def after_subjects  # after_subjects

    # This handles game completion. (Start)
    def on_done(self, play_again_flag: bool) -> None:
        self._clear_frames()
        if play_again_flag:
            self._show_subjects()
        else:
            self.root.destroy()
        # end if
    # end def on_done  # on_done

# end class App  # App
