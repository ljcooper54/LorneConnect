# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Application entry point."""

import tkinter as tk

from .constants import DEBUG_USERNAME
from .db import DB
from .generator import PuzzleGenerator
from .ui_login import LoginWindow
from .ui_subjects import SubjectWindow
from .ui_game import PuzzleGame
from .spinner import GeneratingWindow

class App:
    """Main controller with spinner for generation."""

    def __init__(self, root):
        self.root = root
        self.db = DB()
        self.generator = PuzzleGenerator(self.db)
        self.user = None
        self._show_login()

    def _clear_frames(self):
        for child in list(self.root.winfo_children()):
            if isinstance(child, tk.Frame):
                child.destroy()

    def _show_login(self):
        self._clear_frames()
        LoginWindow(self.root, self.after_login)

    def after_login(self, user: str):
        global DEBUG_USERNAME
        DEBUG_USERNAME = user
        self.user = user
        self.db.ensure_user_stats(user)
        self._show_subjects()

    def _show_subjects(self):
        self._clear_frames()
        self.root.after(0, lambda: SubjectWindow(self.root, self.user, self.db, self.after_subjects))

    def after_subjects(self, subjects: list[str], subject_window: SubjectWindow):
        subject_window.disable()

        # modal spinner / status window
        spinner = tk.Toplevel(self.root)
        spinner.title("Generating Puzzle")
        spinner.geometry("360x190")
        spinner.configure(bg="#e8f0ff")
        spinner.transient(self.root)
        spinner.grab_set()

        title = tk.Label(spinner, text="🧩 Generating Puzzle", bg="#e8f0ff", font=("Helvetica", 15, "bold"))
        title.pack(pady=(14, 6))

        label = tk.Label(spinner, text="Starting…", bg="#e8f0ff", font=("Helvetica", 12), wraplength=330, justify="center")
        label.pack(pady=(0, 10))

        btn_frame = tk.Frame(spinner, bg="#e8f0ff")
        btn_frame.pack(pady=(6, 0))

        dots_state = {"n": 0, "running": True}

        def stop_dots():
            dots_state["running"] = False

        def tick():
            if not dots_state["running"]:
                return
            dots_state["n"] = (dots_state["n"] + 1) % 4
            label.config(text="Generating puzzle" + "." * dots_state["n"])
            spinner.after(250, tick)

        excluded_subjects = [s for s in subjects if normalize_token(s).lower() != "surprise me!"]

        q = queue.Queue()

        def start_worker():
            # clear any old messages
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

            def worker():
                try:
                    puzzle = self.generator.generate(self.user, subjects, excluded_subjects)
                    q.put(("ok", puzzle))
                except Exception as e:
                    q.put(("err", str(e)))

            threading.Thread(target=worker, daemon=True).start()

        def show_error(err_text: str):
            stop_dots()
            for w in btn_frame.winfo_children():
                w.destroy()

            spinner.geometry("440x280")
            title.config(text="⚠️ Generation Failed")
            label.config(text=err_text)

            def try_again():
                for w in btn_frame.winfo_children():
                    w.destroy()
                title.config(text="🧩 Generating Puzzle")
                dots_state["running"] = True
                dots_state["n"] = 0
                tick()
                start_worker()
                poll()

            def change_categories():
                spinner.destroy()
                subject_window.enable()

            tk.Button(btn_frame, text="Try Again", command=try_again, width=12).pack(side=tk.LEFT, padx=8)
            tk.Button(btn_frame, text="Change Categories", command=change_categories, width=16).pack(side=tk.LEFT, padx=8)

        # Start generation
        label.config(text="Generating puzzle")
        tick()
        start_worker()


        def poll():
            try:
                msg = q.get_nowait()
            except queue.Empty:
                self.root.after(120, poll)
                return

            if msg[0] == "err":
                show_error(msg[1])
                return

            spinner.destroy()

            puzzle = msg[1]
            self.db.inc_played(self.user)

            subject_window.destroy()
            self._clear_frames()
            PuzzleGame(self.root, self.user, self.db, self.generator, puzzle, self.on_done)

        poll()

    def on_done(self, play_again: bool):
        self._clear_frames()
        if play_again:
            self._show_subjects()
        else:
            self.root.destroy()

# end class App

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
# end def main
