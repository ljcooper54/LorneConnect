# File: App/main.py | Created/Modified: 2026-03-12
# Copyright 2025 H2so4 Consulting LLC
"""Entry point module.

Exports main() for LorneConnections_run.py and ensures the app window is raised on launch
(helps initial focus on macOS).
"""

from __future__ import annotations

import tkinter as tk

from .app_controller import App


# This is the module entry point called by LorneConnections_run.py. (Start)
def main() -> None:
    root = tk.Tk()
    root.title("Connections")

    App(root)

    # Let Tk compute the natural startup size from actual widgets. (Start)
    root.update_idletasks()
    req_w = max(root.winfo_reqwidth() + 24, 860)
    req_h = max(root.winfo_reqheight() + 24, 560)
    root.geometry(f"{req_w}x{req_h}")
    root.minsize(req_w, req_h)
    # end startup geometry

    # This raises the window on startup (macOS focus helper). (Start)
    def _raise_on_start() -> None:
        try:
            root.lift()
            root.attributes("-topmost", True)
            root.update_idletasks()
            root.focus_force()
            root.attributes("-topmost", False)
        except tk.TclError:
            pass
        # end try/except
    # end def _raise_on_start  # _raise_on_start

    root.after(60, _raise_on_start)
    root.mainloop()
# end def main  # main
