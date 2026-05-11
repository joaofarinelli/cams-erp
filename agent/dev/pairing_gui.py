"""First-launch Tkinter dialog for pairing the agent to a cams-erp account.

User flow:
  1. Web app: cliente -> Devices -> "Adicionar PDV" -> gera pair code (6 dígitos)
  2. Agent: abre janela com campo de API URL (preenchido) + pair code
  3. Clica "Parear" -> POST /pair/verify -> recebe device_token -> grava config.json

We block until the user either pairs successfully or cancels. Tray app starts
after this returns. No env-var editing required.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

import httpx

from config_store import DEFAULT_API, save_config


_PAIR_CODE_RE = re.compile(r"^\d{6}$")


def _pair_with_api(api_base: str, pair_code: str) -> dict | None:
    """Returns server response dict on success, None on failure (after showing
    the error via messagebox)."""
    try:
        r = httpx.post(
            f"{api_base.rstrip('/')}/pair/verify",
            json={"pair_code": pair_code},
            timeout=15,
        )
    except httpx.HTTPError as e:
        messagebox.showerror("Erro de rede", f"Não consegui falar com {api_base}.\n\n{e}")
        return None
    if r.status_code == 200:
        return r.json()
    try:
        detail = r.json().get("detail", r.text)
    except Exception:  # noqa: BLE001
        detail = r.text
    messagebox.showerror("Falha no pareamento", f"HTTP {r.status_code}: {detail}")
    return None


def run_pairing_window() -> dict | None:
    """Show the modal pairing window. Returns the saved config dict on success
    (also persisted to disk), or None if the user closed the window."""
    root = tk.Tk()
    root.title("cams-erp — parear PDV")
    root.geometry("420x260")
    root.resizable(False, False)

    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "aqua" in style.theme_names():
        style.theme_use("aqua")

    result: dict | None = None

    main = ttk.Frame(root, padding=20)
    main.pack(fill="both", expand=True)

    ttk.Label(
        main,
        text="Cole o código de 6 dígitos gerado no painel web\n(Devices → Adicionar PDV).",
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    ttk.Label(main, text="API:").pack(anchor="w")
    api_var = tk.StringVar(value=DEFAULT_API)
    api_entry = ttk.Entry(main, textvariable=api_var, width=48)
    api_entry.pack(fill="x", pady=(0, 10))

    ttk.Label(main, text="Código de pareamento (6 dígitos):").pack(anchor="w")
    code_var = tk.StringVar()
    code_entry = ttk.Entry(main, textvariable=code_var, width=10, font=("TkDefaultFont", 14))
    code_entry.pack(anchor="w", pady=(0, 10))
    code_entry.focus_set()

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(main, textvariable=status_var, foreground="#888")
    status_label.pack(anchor="w")

    def attempt_pair() -> None:
        nonlocal result
        api = api_var.get().strip()
        code = code_var.get().strip()
        if not _PAIR_CODE_RE.match(code):
            status_var.set("Código precisa ter exatamente 6 dígitos.")
            return
        if not api.startswith(("http://", "https://")):
            status_var.set("API URL inválida.")
            return
        status_var.set("Pareando…")
        root.update_idletasks()
        resp = _pair_with_api(api, code)
        if resp is None:
            status_var.set("Tente de novo.")
            return
        cfg = {
            "api_base": api.rstrip("/"),
            "device_token": resp["device_token"],
            "device_id": resp.get("device_id"),
        }
        save_config(cfg)
        result = cfg
        root.destroy()

    btns = ttk.Frame(main)
    btns.pack(fill="x", pady=(14, 0))
    ttk.Button(btns, text="Cancelar", command=root.destroy).pack(side="right", padx=(8, 0))
    ttk.Button(btns, text="Parear", command=attempt_pair).pack(side="right")

    root.bind("<Return>", lambda _e: attempt_pair())
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    # Center on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()
    return result
