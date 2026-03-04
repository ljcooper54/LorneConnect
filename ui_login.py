# Copyright 2025 H2so4 Consulting LLC
# 2026-03-03: Persist last login email in project .env; Return-to-submit on password; strip CR/LF.
# Login screen with whitelist + password support. (Start)

import tkinter as tk
from tkinter import messagebox
import re
from pathlib import Path


# Resolve the project root .env: .../Connections/App/ui_login.py -> .../Connections/.env
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
LAST_LOGIN_KEY = "LORNECONNECTIONS_LAST_LOGIN"


# Read a single key from a .env file. (Start)
def _dotenv_get(path: Path, key: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""

    prefix = key + "="
    for line in lines:
        s = line.strip()
        if (not s) or s.startswith("#"):
            continue
        if s.startswith(prefix):
            return s[len(prefix):].strip().strip('"').strip("'")
    return ""
# end _dotenv_get


# Set/update a single key in a .env file while preserving everything else. (Start)
def _dotenv_set(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []

    prefix = key + "="
    out: list[str] = []
    replaced = False

    for line in lines:
        s = line.strip()
        if s.startswith(prefix):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(f"{key}={value}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
# end _dotenv_set


class LoginWindow(tk.Toplevel):
    # Create and manage the login dialog window. (Start)
    def __init__(self, parent, db, on_success):
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.on_success = on_success

        self.title("Login")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="Email").pack(padx=20, pady=(20, 5))
        self.email_entry = tk.Entry(self, width=40)
        self.email_entry.bind("<Return>", lambda _e: self.submit())
        self.email_entry.pack(padx=20)

        last = _dotenv_get(ENV_PATH, LAST_LOGIN_KEY).strip()
        if last:
            self.email_entry.insert(0, last)
            self.email_entry.select_range(0, tk.END)

        tk.Label(self, text="Password").pack(padx=20, pady=(15, 5))
        self.password_entry = tk.Entry(self, width=40, show="*")
        self.password_entry.bind("<Return>", lambda _e: self.submit())
        self.password_entry.pack(padx=20)

        tk.Button(self, text="Login", command=self.submit).pack(pady=20)

        self.email_entry.focus_set()
    # end __init__

    # Validate simple email format. (Start)
    def _valid_email(self, email: str) -> bool:
        return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))
    # end _valid_email

    # Submit login attempt. (Start)
    def submit(self):
        try:
            email = self.email_entry.get().strip().lower()
            raw = self.password_entry.get()
            raw = raw.replace("\r", "").replace("\n", "")
            password = raw.strip()

            if not self._valid_email(email):
                messagebox.showerror("Invalid Email", "Enter a valid email address.", parent=self)
                return

            # Persist last login across runs.
            try:
                _dotenv_set(ENV_PATH, LAST_LOGIN_KEY, email)
            except Exception:
                # Non-fatal: login can still proceed even if .env is not writable.
                pass

            # Must exist (whitelist)
            if not self.db.user_exists(email):
                messagebox.showerror("Not Authorized", "This email is not authorized.", parent=self)
                return

            # First login: no password set yet
            has_password = True
            if hasattr(self.db, "user_has_password"):
                has_password = self.db.user_has_password(email)

            if not has_password:
                if not password:
                    messagebox.showerror("Set Password", "Please enter a password.", parent=self)
                    return

                # Support either method name
                if hasattr(self.db, "set_user_password"):
                    self.db.set_user_password(email, password)
                else:
                    self.db.set_password(email, password)

                messagebox.showinfo("Password Set", "Password created successfully.", parent=self)

            else:
                # Verify password
                verified = False
                if hasattr(self.db, "verify_user_password"):
                    verified = self.db.verify_user_password(email, password)
                else:
                    verified = self.db.verify_password(email, password)

                if not verified:
                    messagebox.showerror("Login Failed", "Incorrect password.", parent=self)
                    return

            self.grab_release()
            self.destroy()
            self.on_success(email)

        except Exception as e:
            messagebox.showerror("Login Error", f"{type(e).__name__}: {e}", parent=self)
    # end submit
# end LoginWindow
