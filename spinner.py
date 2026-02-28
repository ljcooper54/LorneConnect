# File: App/spinner.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Generating window UI.

Requirements:
- Title
- Animated spinner/dots line
- Persistent status log: append lines (do not overwrite)
- Change spinner color each time a status line is appended
- Modal focus/grab so it doesn't hide under other windows
"""

from __future__ import annotations

import itertools
import tkinter as tk


# This GeneratingWindow provides a modal progress dialog with cancel + persistent log. (Start)
class GeneratingWindow:
    """Modal generating dialog with animated spinner + status log."""

    # This initializes the window and widgets. (Start)
    def __init__(
        self,
        root: tk.Tk,
        title: str = "Generating Puzzle",
        message: str = "Starting…",
        width: int = 520,
        height: int = 300,
    ):
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.title(title)
        self._win.geometry(f"{width}x{height}")
        self._win.configure(bg="#e8f0ff")
        self._win.transient(root)
        self._win.grab_set()

        self._title = tk.Label(
            self._win,
            text="🧩 " + title,
            bg="#e8f0ff",
            font=("Helvetica", 15, "bold"),
        )
        self._title.pack(pady=(14, 8))

        # Spinner/dots line (foreground color will cycle). (Start)
        self._dots_label = tk.Label(
            self._win,
            text="",
            bg="#e8f0ff",
            font=("Helvetica", 12),
            wraplength=max(420, width - 30),
            justify="center",
        )
        self._dots_label.pack(pady=(0, 6))
        # end spinner line

        # Persistent log area (append-only). (Start)
        log_frame = tk.Frame(self._win, bg="#e8f0ff")
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._log = tk.Text(
            log_frame,
            height=8,
            wrap="word",
            state="disabled",
            font=("Helvetica", 11),
        )
        self._log.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(log_frame, command=self._log.yview)
        scroll.pack(side="right", fill="y")
        self._log.config(yscrollcommand=scroll.set)
        # end log area

        self.button_frame = tk.Frame(self._win, bg="#e8f0ff")
        self.button_frame.pack(pady=(0, 10))

        self._dots_state = {"n": 0, "running": False, "base": ""}

        # Color cycle for spinner changes each appended status line.
        self._color_cycle = itertools.cycle(
            ["#0b5394", "#38761d", "#a61c00", "#674ea7", "#134f5c", "#783f04"]
        )

        # Seed the log with the initial message.
        self.append_status(message)

        self.focus_modal()
    # end def __init__  # __init__

    # This forces the modal to the front and grabs keyboard focus. (Start)
    def focus_modal(self) -> None:
        try:
            self._win.lift()
            self._win.attributes("-topmost", True)
            self._win.update_idletasks()
            self._win.focus_force()
            self._win.attributes("-topmost", False)
        except tk.TclError:
            pass
        # end try/except
    # end def focus_modal  # focus_modal

    # This starts an animated dots indicator. (Start)
    def start_dots(self, base_text: str = "Generating puzzle") -> None:
        self._dots_state["running"] = True
        self._dots_state["n"] = 0
        self._dots_state["base"] = base_text

        def tick() -> None:
            if not self._dots_state["running"]:
                return
            # end if
            self._dots_state["n"] = (self._dots_state["n"] + 1) % 4
            base = self._dots_state["base"]
            self._dots_label.config(text=base + "." * self._dots_state["n"])
            self._win.after(250, tick)
        # end def tick  # tick

        tick()
    # end def start_dots  # start_dots

    # This stops dots animation and clears spinner line. (Start)
    def stop_dots(self) -> None:
        self._dots_state["running"] = False
        try:
            self._dots_label.config(text="")
        except tk.TclError:
            pass
        # end try/except
    # end def stop_dots  # stop_dots

    # This appends a persistent status line and cycles spinner color. (Start)
    def append_status(self, line: str) -> None:
        text = (line or "").strip()
        if not text:
            return
        # end if

        # Cycle spinner color on every new line.
        try:
            self._dots_label.config(fg=next(self._color_cycle))
        except tk.TclError:
            pass
        # end try/except

        try:
            self._log.config(state="normal")
            self._log.insert(tk.END, text + "\n")
            self._log.see(tk.END)
            self._log.config(state="disabled")
        except tk.TclError:
            pass
        # end try/except
    # end def append_status  # append_status

    # This keeps a compatibility API: treat set_message as append. (Start)
    def set_message(self, message: str) -> None:
        self.append_status(message)
    # end def set_message  # set_message

    # This sets the window title. (Start)
    def set_title(self, title: str) -> None:
        self._win.title(title)
        self._title.config(text="🧩 " + title)
    # end def set_title  # set_title

    # This destroys the modal window safely. (Start)
    def destroy(self) -> None:
        try:
            self._win.grab_release()
        except tk.TclError:
            pass
        # end try/except
        try:
            self._win.destroy()
        except tk.TclError:
            pass
        # end try/except
    # end def destroy  # destroy

# end class GeneratingWindow  # GeneratingWindow
