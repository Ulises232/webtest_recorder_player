"""UI components for the "Modificación de Matriz" workflow."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import SECONDARY


def build_modificacion_matriz_view(parent: tb.Frame) -> None:
    """Render the placeholder content for matrix editing."""

    for child in parent.winfo_children():
        child.destroy()

    tb.Label(parent, text="Modificación de Matriz", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W, pady=(0, 6))
    tb.Label(
        parent,
        text="Busca, abre y edita matrices existentes.",
        bootstyle=SECONDARY,
    ).pack(anchor=tk.W)
    tb.Separator(parent).pack(fill=tk.X, pady=10)
