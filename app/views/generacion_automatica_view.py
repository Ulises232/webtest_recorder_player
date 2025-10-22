"""UI builder for the "Generación Automática" workflow."""

from __future__ import annotations

import csv
import datetime
import itertools
import os
import re
from typing import Callable
import tkinter as tk
from tkinter import messagebox, ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import DANGER, INFO, PRIMARY, SECONDARY


def build_generacion_automatica_view(
    root: tk.Misc,
    parent: tb.Frame,
    bind_mousewheel: Callable[[tk.Widget, Callable[..., None]], None],
) -> None:
    """Populate the automatic matrix generation view inside the given parent."""

    for child in parent.winfo_children():
        child.destroy()

    ga_matrix_name = tk.StringVar(value="")
    ga_status = tk.StringVar(value="Listo.")
    variables: list[dict[str, list[str] | str]] = []
    preview_rows: list[list[str]] = []

    top = tb.Labelframe(parent, text="Datos de la matriz", padding=10)
    top.pack(fill=tk.X)
    tb.Label(top, text="Nombre de la matriz").grid(row=0, column=0, sticky="w", padx=(2, 8), pady=6)
    ent_name = tb.Entry(top, textvariable=ga_matrix_name, width=40)
    ent_name.grid(row=0, column=1, sticky="we", pady=6)
    top.grid_columnconfigure(1, weight=1)

    capture = tb.Labelframe(parent, text="Captura de variables", padding=10)
    capture.pack(fill=tk.X, pady=(8, 0))
    tb.Label(capture, text="Variable").grid(row=0, column=0, sticky="w")
    tb.Label(capture, text="Puede valer (separado por comas)").grid(row=0, column=1, sticky="w")
    var_name = tk.StringVar(value="")
    var_values = tk.StringVar(value="")
    ent_var = tb.Entry(capture, textvariable=var_name, width=24)
    ent_var.grid(row=1, column=0, sticky="we", padx=(0, 8), pady=(0, 8))
    ent_vals = tb.Entry(capture, textvariable=var_values, width=50)
    ent_vals.grid(row=1, column=1, sticky="we", padx=(0, 8), pady=(0, 8))

    def render_variables() -> None:
        """Render the list of configured variables."""

        for widget in vars_box.winfo_children():
            widget.destroy()
        if not variables:
            tb.Label(vars_box, text="(Sin variables)", bootstyle=SECONDARY).pack(anchor="w")
            return
        for index, var in enumerate(variables):
            row = tb.Frame(vars_box)
            row.pack(fill=tk.X, pady=4)
            tb.Label(row, text=str(var["name"]), font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
            tb.Label(row, text="  |  ").pack(side=tk.LEFT)
            tb.Label(row, text=", ".join(var["values"]), bootstyle=SECONDARY).pack(side=tk.LEFT)
            tb.Button(row, text="✏️ Editar", bootstyle=SECONDARY, command=lambda idx=index: edit_var(idx)).pack(
                side=tk.RIGHT, padx=4
            )
            tb.Button(row, text="❌ Eliminar", bootstyle=DANGER, command=lambda idx=index: delete_var(idx)).pack(
                side=tk.RIGHT, padx=4
            )

    def edit_var(index: int) -> None:
        """Open a dialog to edit the selected variable."""

        data = variables[index]
        dialog = tk.Toplevel(root)
        dialog.title(f"Editar {data['name']}")
        dialog.geometry("420x200")
        name_var = tk.StringVar(value=str(data["name"]))
        values_var = tk.StringVar(value=", ".join(data["values"]))
        tb.Label(dialog, text="Variable").pack(anchor="w", padx=10, pady=(10, 2))
        tb.Entry(dialog, textvariable=name_var).pack(fill=tk.X, padx=10)
        tb.Label(dialog, text="Valores (coma)").pack(anchor="w", padx=10, pady=(10, 2))
        tb.Entry(dialog, textvariable=values_var).pack(fill=tk.X, padx=10)

        def commit() -> None:
            """Store the edited values when validation passes."""

            name = name_var.get().strip()
            values = [value.strip() for value in values_var.get().split(",") if value.strip()]
            if not name or not values:
                messagebox.showwarning("Faltan datos", "Nombre y valores no pueden quedar vacíos.")
                return
            if any(
                idx != index and str(variables[idx]["name"]).lower() == name.lower()
                for idx in range(len(variables))
            ):
                messagebox.showwarning("Duplicado", f"Ya existe una variable con nombre '{name}'.")
                return
            variables[index] = {"name": name, "values": values}
            render_variables()
            dialog.destroy()

        tb.Button(dialog, text="Guardar", bootstyle=PRIMARY, command=commit).pack(side=tk.RIGHT, padx=10, pady=12)
        tb.Button(dialog, text="Cancelar", bootstyle=SECONDARY, command=dialog.destroy).pack(side=tk.RIGHT, pady=12)

    def delete_var(index: int) -> None:
        """Remove a variable after confirming with the user."""

        name = str(variables[index]["name"])
        if messagebox.askyesno("Confirmar", f"¿Eliminar variable '{name}'?"):
            variables.pop(index)
            render_variables()

    def add_variable() -> None:
        """Append a variable to the working matrix definition."""

        name = var_name.get().strip()
        values = [value.strip() for value in var_values.get().split(",") if value.strip()]
        if not name:
            messagebox.showwarning("Falta dato", "Debes capturar el nombre de la variable.")
            return
        if not values:
            messagebox.showwarning("Falta dato", "Debes capturar al menos un valor para la variable.")
            return
        if any(str(item["name"]).lower() == name.lower() for item in variables):
            messagebox.showwarning("Duplicado", f"La variable '{name}' ya existe.")
            return
        variables.append({"name": name, "values": values})
        var_name.set("")
        var_values.set("")
        render_variables()
        ent_var.focus_set()

    tb.Button(capture, text="Agregar variable", bootstyle=PRIMARY, command=add_variable).grid(
        row=1, column=2, sticky="w"
    )
    capture.grid_columnconfigure(0, weight=1)
    capture.grid_columnconfigure(1, weight=4)

    vars_box = tb.Frame(capture)
    vars_box.grid(row=2, column=0, columnspan=3, sticky="we")
    render_variables()

    template_box = tb.Labelframe(parent, text="Plantilla de caso de prueba", padding=10)
    template_box.pack(fill=tk.X, pady=(8, 0))
    rules_box = tb.Labelframe(parent, text="Reglas de invalidez (Var=Val && Var=Val => inválido)", padding=10)
    rules_box.pack(fill=tk.X, pady=(8, 0))
    template_text = tk.Text(template_box, height=3)
    template_text.pack(fill=tk.X)
    rules_text = tk.Text(rules_box, height=4)
    rules_text.pack(fill=tk.X)

    def default_template() -> str:
        """Return the default test case template."""

        if not variables:
            return "Validar el sistema"
        parts = [f"{item['name']} es {{{item['name']}}}" for item in variables]
        return "Validar el sistema cuando " + ", ".join(parts)

    def parse_rules(text: str) -> list[dict[str, object]]:
        """Parse the invalidation rules typed by the user."""

        rules: list[dict[str, object]] = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if "=>" not in line:
                continue
            conditions, result = [part.strip() for part in line.split("=>", 1)]
            if not re.search(r"inv[aá]lido", result, flags=re.IGNORECASE):
                continue
            tokens = re.split(r"(&&|\|\|)", conditions)
            terms = [token.strip() for token in tokens if token.strip()]
            cond_terms: list[dict[str, str]] = []
            operators: list[str] = []
            for token in terms:
                if token in ("&&", "||"):
                    operators.append(token)
                else:
                    key, _, value = token.partition("=")
                    cond_terms.append({"key": key.strip(), "val": value.strip()})
            rules.append({"parts": cond_terms, "ops": operators})
        return rules

    preview_box = tb.Labelframe(parent, text="Vista previa", padding=10)
    preview_box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
    buttons_row = tb.Frame(preview_box)
    buttons_row.pack(fill=tk.X)

    tree = ttk.Treeview(preview_box, show="headings", height=12)
    vsb = ttk.Scrollbar(preview_box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)

    def clear_tree() -> None:
        """Reset the preview tree and remove all rows."""

        for column in tree["columns"]:
            try:
                tree.heading(column, text="")
            except Exception:
                continue
        tree.delete(*tree.get_children())
        tree["columns"] = ()

    def reset_form(confirm: bool = True) -> None:
        """Clear the current configuration and start over."""

        has_data = bool(variables or tree.get_children(""))
        if confirm and has_data:
            if not messagebox.askyesno("Nueva matriz", "¿Limpiar la captura y comenzar otra matriz?"):
                return
        variables.clear()
        render_variables()
        ga_matrix_name.set("")
        template_text.delete("1.0", "end")
        rules_text.delete("1.0", "end")
        clear_tree()
        count_label.configure(text="")
        ga_status.set("Listo.")
        try:
            ent_name.focus_set()
        except Exception:
            pass

    def evaluate_rules(rules: list[dict[str, object]], row_values: list[str], var_order: list[str]) -> bool:
        """Return True when the given combination is invalid according to the rules."""

        def term_value(term: dict[str, str]) -> bool:
            """Check whether a single condition matches the provided row values."""

            try:
                index = var_order.index(term["key"])
            except ValueError:
                return False
            return row_values[index] == term["val"]

        for rule in rules:
            value: bool | None = None
            for idx, term in enumerate(rule["parts"]):
                term_matches = term_value(term)  # type: ignore[arg-type]
                if value is None:
                    value = term_matches
                else:
                    operator = rule["ops"][idx - 1] if idx - 1 < len(rule["ops"]) else "&&"
                    value = (value and term_matches) if operator == "&&" else (value or term_matches)
            if value:
                return True
        return False

    def generate_preview() -> None:
        """Create the preview matrix using the captured variables."""

        missing: list[str] = []
        if not ga_matrix_name.get().strip():
            missing.append("Nombre de la matriz")
        if not variables:
            missing.append("Al menos una variable")
        else:
            for var in variables:
                if not var["values"]:
                    missing.append(f"Valores de {var['name']}")
        if missing:
            messagebox.showwarning("Faltan datos", "Faltan: " + ", ".join(missing))
            return

        var_names = [str(var["name"]) for var in variables]
        template = template_text.get("1.0", "end").strip() or default_template()
        rules = parse_rules(rules_text.get("1.0", "end"))

        combos = list(itertools.product(*[var["values"] for var in variables])) if variables else []
        preview_rows.clear()
        valid_count = 0
        invalid_count = 0

        for index, combo in enumerate(combos, start=1):
            test_case = template
            for name, value in zip(var_names, combo):
                test_case = test_case.replace("{" + name + "}", str(value))
            is_invalid = evaluate_rules(rules, list(combo), var_names)
            is_valid_text = "No" if is_invalid else "Sí"
            if is_invalid:
                invalid_count += 1
            else:
                valid_count += 1
            row = [f"CASO {index}", *combo, test_case, is_valid_text, ""]
            preview_rows.append(row)

        clear_tree()
        columns = ["NUMERO CASO DE PRUEBA", *var_names, "Caso de prueba", "¿Válido?", "PROCESAR"]
        tree["columns"] = columns
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=160, anchor="w")
        for row in preview_rows:
            tree.insert("", "end", values=row)

        count_label.configure(
            text=f"Total: {len(preview_rows)}  •  Válidos: {valid_count}  •  Inválidos: {invalid_count}"
        )
        ga_status.set("Vista previa generada.")

    tb.Button(buttons_row, text="Generar vista previa", bootstyle=INFO, command=generate_preview).pack(side=tk.LEFT)
    count_label = tb.Label(preview_box, text="", bootstyle=SECONDARY)
    count_label.pack(anchor="w", pady=(6, 6))

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    bind_mousewheel(tree, tree.yview)

    toolbar = tb.Frame(parent)
    toolbar.pack(fill=tk.X, pady=(8, 0))

    def sanitize_filename(name: str) -> str:
        """Return a safe filename derived from the provided name."""

        return re.sub(r'[\\/:*?"<>|]+', "_", name.strip())

    def save_csv() -> None:
        """Persist the preview to a CSV file within the templates directory."""

        rows = [tree.item(child, "values") for child in tree.get_children("")]
        if not rows:
            messagebox.showwarning("Sin datos", "Primero genera la vista previa.")
            return
        base = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base, "template_matrices")
        os.makedirs(target_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{sanitize_filename(ga_matrix_name.get())}_{timestamp}.csv"
        path = os.path.join(target_dir, filename)
        columns = tree["columns"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as handler:
                writer = csv.writer(handler)
                writer.writerow(columns)
                writer.writerows(rows)
            ga_status.set(f"Guardado: {path}")
            messagebox.showinfo("Éxito", f"Matriz guardada en:\n{path}")
        except Exception as exc:  # pragma: no cover - Tkinter handles GUI feedback
            ga_status.set("ERROR al guardar CSV")
            messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{exc}")

    tb.Button(toolbar, text="Descargar CSV", bootstyle=PRIMARY, command=save_csv).pack(side=tk.LEFT)
    tb.Button(
        toolbar,
        text="Generar otra matriz",
        bootstyle=SECONDARY,
        command=lambda: reset_form(True),
    ).pack(side=tk.LEFT, padx=(8, 0))
    tb.Label(toolbar, textvariable=ga_status, bootstyle=SECONDARY).pack(side=tk.LEFT, padx=12)

