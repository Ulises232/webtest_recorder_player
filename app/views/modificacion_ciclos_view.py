"""UI components for the "Modificación de Ciclos" workflow."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import SECONDARY


def build_modificacion_ciclos_view(parent: tb.Frame) -> None:
    """Render the placeholder content for the cycle update view."""

    for child in parent.winfo_children():
        child.destroy()

    tb.Label(parent, text="Modificación de Ciclos", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W, pady=(0, 6))
    tb.Label(
        parent,
        text="Actualiza ciclos previamente creados.",
        bootstyle=SECONDARY,
    ).pack(anchor=tk.W)
    tb.Separator(parent).pack(fill=tk.X, pady=10)
