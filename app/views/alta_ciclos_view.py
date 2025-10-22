"""UI components for the "Alta de Ciclos" workflow."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import SECONDARY


def build_alta_ciclos_view(parent: tb.Frame) -> None:
    """Render the placeholder content for the cycle creation view."""

    for child in parent.winfo_children():
        child.destroy()

    tb.Label(parent, text="Alta de Ciclos", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W, pady=(0, 6))
    tb.Label(
        parent,
        text="Crea ciclos nuevos para su uso en matrices.",
        bootstyle=SECONDARY,
    ).pack(anchor=tk.W)
    tb.Separator(parent).pack(fill=tk.X, pady=10)
