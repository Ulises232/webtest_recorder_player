"""UI builder for the 'Generación Manual' workflow."""

from __future__ import annotations

import csv
import datetime
import os
import re
from typing import Callable
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403


def build_generacion_manual_view(
    root: tk.Misc,
    parent: tb.Frame,
    bind_mousewheel: Callable[[tk.Widget, Callable[..., None]], None],
) -> None:
    """Populate the manual matrix generation view inside the target frame."""

    for _w in parent.winfo_children():
        _w.destroy()
    
    gm_matrix_name = tk.StringVar(value="")
    gm_mode = tk.StringVar(value="")
    gm_status = tk.StringVar(value="Elige cómo quieres trabajar (importar o captura manual).")
    gm_case_counter = tk.IntVar(value=1)
    gm_dyncols = []
    
    def _sanitize_filename(name: str) -> str:
        """Auto-generated docstring for `_sanitize_filename`."""
        name = re.sub(r'[\\/:*?"<>|]+', "_", name.strip()); return name
    
    def _normalize_header(s: str) -> str:
        """Auto-generated docstring for `_normalize_header`."""
        s = (s or "").strip().lower()
        for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","¿":"", "?":""}.items():
            s = s.replace(a,b)
        s = re.sub(r'\s+', ' ', s)
        return s
    
    REQ_LEFT  = "numero caso de prueba"
    REQ_RIGHT = "caso de prueba"
    REQ_FIXED_TAIL = ["¿válido?", "procesar"]
    
    def _headers_ok(headers):
        """Auto-generated docstring for `_headers_ok`."""
        norm = [_normalize_header(h) for h in headers]
        fixed_norm = [_normalize_header(h) for h in REQ_FIXED_TAIL]
        if REQ_LEFT not in norm: return False, "Falta columna 'NUMERO CASO DE PRUEBA'"
        if REQ_RIGHT not in norm: return False, "Falta columna 'Caso de prueba'"
        miss = [REQ_FIXED_TAIL[i] for i,h in enumerate(fixed_norm) if h not in norm]
        if miss: return False, f"Faltan columnas: {', '.join(miss)}"
        if norm.index(REQ_LEFT) >= norm.index(REQ_RIGHT):
            return False, "'NUMERO CASO DE PRUEBA' debe ir antes que 'Caso de prueba'"
        return True, ""
    
    def _split_headers(headers):
        """Auto-generated docstring for `_split_headers`."""
        norm = [_normalize_header(h) for h in headers]
        li = norm.index(REQ_LEFT); ri = norm.index(REQ_RIGHT)
        left = [headers[li]]; dyn = headers[li+1:ri]; tail = headers[ri:]
        return left, dyn, tail
    
    def _tree_set_columns(tree, headers):
        """Auto-generated docstring for `_tree_set_columns`."""
        tree['columns'] = headers
        for c in headers:
            try: tree.heading(c, text=c); tree.column(c, width=160, anchor="w")
            except Exception: pass
    
    def _renumber_cases(tree):
        """Auto-generated docstring for `_renumber_cases`."""
        cols = list(tree['columns'])
        norm = [_normalize_header(h) for h in cols]
        if REQ_LEFT not in norm: return
        idx = norm.index(REQ_LEFT)
        for i, item in enumerate(tree.get_children(""), start=1):
            vals = list(tree.item(item, 'values'))
            if idx < len(vals):
                vals[idx] = f"CASO {i}"
                tree.item(item, values=vals)
    
    def _read_csv_any_encoding(path):
        """Auto-generated docstring for `_read_csv_any_encoding`."""
        encs = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        last_err = None
        for enc in encs:
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    sample = f.read(4096); f.seek(0)
                    delim = ","
                    if sample.count(";") > sample.count(",") and ";" in sample: delim = ";"
                    elif "\t" in sample and sample.count("\t") > 0: delim = "\t"
                    reader = csv.reader(f, delimiter=delim)
                    headers = next(reader, [])
                    rows = list(reader)
                    return headers, rows
            except Exception as ex:
                last_err = ex; continue
        raise last_err if last_err else Exception("No se pudo leer el CSV.")
    
    # Selector de modo
    mode_box = tb.Labelframe(parent, text="¿Cómo deseas trabajar?", padding=10); mode_box.pack(fill=X)
    tb.Radiobutton(mode_box, text="Importar CSV/XLSX", variable=gm_mode, value="import", command=lambda: _show_mode()).pack(side=LEFT, padx=(0,12))
    tb.Radiobutton(mode_box, text="Captura manual",   variable=gm_mode, value="manual", command=lambda: _show_mode()).pack(side=LEFT)
    
    status_lbl = tb.Label(parent, textvariable=gm_status, bootstyle=SECONDARY)
    status_lbl.pack(anchor="w", padx=6, pady=(6,0))
    
    top = tb.Labelframe(parent, text="Datos de la matriz", padding=10)
    tb.Label(top, text="Nombre de la matriz").grid(row=0, column=0, sticky="w", padx=(2,8), pady=6)
    tb.Entry(top, textvariable=gm_matrix_name, width=40).grid(row=0, column=1, sticky="we", pady=6)
    top.grid_columnconfigure(1, weight=1)
    
    # Barra única (evita duplicados)
    gm_toolbar = tb.Frame(parent)
    def _build_toolbar():
        """Auto-generated docstring for `_build_toolbar`."""
        for w in gm_toolbar.winfo_children(): w.destroy()
        tb.Button(gm_toolbar, text="Guardar CSV", bootstyle=PRIMARY,
                command=lambda: _save_from_tree(imp_tree if gm_mode.get()=='import' else man_tree)).pack(side=LEFT)
        tb.Button(gm_toolbar, text="Nueva matriz", bootstyle=SECONDARY,
                command=lambda: _gm_reset_form(True)).pack(side=LEFT, padx=(8,0))
    _build_toolbar()
    
    def _save_from_tree(tree):
        """Auto-generated docstring for `_save_from_tree`."""
        rows = [tree.item(ch, 'values') for ch in tree.get_children("")]
        if not rows:
            messagebox.showwarning("Sin datos", "No hay filas para guardar."); return
        if not gm_matrix_name.get().strip():
            messagebox.showwarning("Falta nombre", "Captura el nombre de la matriz."); return
        base = os.path.dirname(os.path.abspath(__file__)); target_dir = os.path.join(base, "template_matrices"); os.makedirs(target_dir, exist_ok=True)
        dt = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); fname = f"{_sanitize_filename(gm_matrix_name.get())}_{dt}.csv"
        fpath = os.path.join(target_dir, fname)
        try:
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(tree['columns'])
                for r in rows: w.writerow(r)
            gm_status.set(f"Guardado: {fpath}"); messagebox.showinfo("Éxito", f"Matriz guardada en:\n{fpath}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{ex}")
    
    def _gm_clear_tree(tree):
        """Auto-generated docstring for `_gm_clear_tree`."""
        if not isinstance(tree, ttk.Treeview): return
        for c in tree['columns']:
            try: tree.heading(c, text="")
            except Exception: pass
        tree.delete(*tree.get_children()); tree['columns'] = ()
    
    def _gm_reset_form(confirm=True):
        """Auto-generated docstring for `_gm_reset_form`."""
        has_rows = False
        try: has_rows = bool(imp_tree.get_children("") or man_tree.get_children(""))
        except Exception: pass
        has_dyn = bool(gm_dyncols); has_name = bool(gm_matrix_name.get().strip())
        if confirm and (has_rows or has_dyn or has_name):
            if not messagebox.askyesno("Nueva matriz", "¿Limpiar todo para comenzar una nueva matriz?"): return
        gm_matrix_name.set(""); gm_case_counter.set(1); gm_dyncols.clear()
        try: _gm_clear_tree(imp_tree); _gm_clear_tree(man_tree)
        except Exception: pass
        gm_status.set("Elige cómo quieres trabajar (importar o captura manual).")
        gm_mode.set(""); _show_mode()
    
    import_frame = tb.Frame(parent)
    manual_frame = tb.Frame(parent)
    
    # --- Importar ---
    imp_top = tb.Labelframe(import_frame, text="Importar archivo", padding=10)
    imp_path = tk.StringVar(value="")
    tb.Entry(imp_top, textvariable=imp_path).grid(row=0, column=0, sticky="we", padx=(0,6))
    tb.Button(imp_top, text="Examinar...", bootstyle=SECONDARY, command=lambda: _browse_import()).grid(row=0, column=1)
    imp_top.grid_columnconfigure(0, weight=1)
    imp_info = tb.Label(import_frame, text="Selecciona un CSV o XLSX con estructura compatible.", bootstyle=SECONDARY)
    imp_prev = tb.Labelframe(import_frame, text="Vista previa (importado)", padding=10)
    imp_tv_wrap = tb.Frame(imp_prev)
    imp_tree = ttk.Treeview(imp_tv_wrap, show="headings", height=10)
    imp_vsb = ttk.Scrollbar(imp_tv_wrap, orient="vertical", command=imp_tree.yview); imp_tree.configure(yscrollcommand=imp_vsb.set)
    imp_tree.pack(side=LEFT, fill=BOTH, expand=True); imp_vsb.pack(side=RIGHT, fill=Y)
    bind_mousewheel(imp_tree, imp_tree.yview)
    imp_actions = tb.Frame(import_frame)
    
    def _imp_delete_selected():
        """Auto-generated docstring for `_imp_delete_selected`."""
        sel = imp_tree.selection()
        if not sel: return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {len(sel)} fila(s) seleccionada(s)?"): return
        for it in sel: imp_tree.delete(it)
        _renumber_cases(imp_tree); gm_status.set("Fila(s) eliminada(s).")
    
    def _imp_clear_all():
        """Auto-generated docstring for `_imp_clear_all`."""
        if not imp_tree.get_children(""): return
        if not messagebox.askyesno("Vaciar tabla", "¿Vaciar todas las filas importadas?"): return
        imp_tree.delete(*imp_tree.get_children()); gm_status.set("Tabla vacía.")
    
    imp_tree.bind("<Delete>", lambda e: (_imp_delete_selected(), "break"))
    
    tb.Button(imp_actions, text="Eliminar fila", bootstyle=DANGER, command=_imp_delete_selected).pack(side=LEFT)
    tb.Button(imp_actions, text="Vaciar tabla", bootstyle=SECONDARY, command=_imp_clear_all).pack(side=LEFT, padx=(8,0))
    
    # --- Manual ---
    cols_bar = tb.Labelframe(manual_frame, text="Columnas dinámicas", padding=10)
    _gm_newcol = tk.StringVar(value="")
    tb.Entry(cols_bar, textvariable=_gm_newcol, width=28).pack(side=LEFT)
    def _add_dyncol_and_refresh():
        """Auto-generated docstring for `_add_dyncol_and_refresh`."""
        name = _gm_newcol.get().strip()
        if not name: return
        if name in gm_dyncols: messagebox.showwarning("Duplicado", f"La columna '{name}' ya existe."); return
        gm_dyncols.append(name); _gm_newcol.set("")
        _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
    tb.Button(cols_bar, text="Agregar columna", bootstyle=SECONDARY, command=_add_dyncol_and_refresh).pack(side=LEFT, padx=(8,0))
    tb.Button(cols_bar, text="Cargar desde plantilla (CSV)", bootstyle=SECONDARY, command=lambda: _load_dyncols_from_template()).pack(side=LEFT, padx=(8,0))
    
    chips_holder = tb.Frame(cols_bar); chips_holder.pack(fill=X, pady=(8,0))
    
    def _render_dynchips():
        """Auto-generated docstring for `_render_dynchips`."""
        for w in chips_holder.winfo_children(): w.destroy()
        if not gm_dyncols:
            tb.Label(chips_holder, text="(Sin columnas dinámicas)", bootstyle=SECONDARY).pack(anchor="w"); return
        for i, col in enumerate(gm_dyncols):
            chip = tb.Frame(chips_holder, bootstyle=SECONDARY); chip.pack(side=LEFT, padx=4)
            tb.Label(chip, text=col).pack(side=LEFT, padx=(6,2), pady=2)
            def _make_cmd(name=col):
                """Auto-generated docstring for `_make_cmd`."""
                def _cmd():
                    """Auto-generated docstring for `_cmd`."""
                    if man_tree.get_children(""):
                        if not messagebox.askyesno("Eliminar columna", f"Hay filas capturadas.\n¿Eliminar la columna '{name}' y ajustar la tabla?"): return
                    old = list(gm_dyncols); new_dyn = [c for c in old if c != name]
                    rows = [man_tree.item(ch, 'values') for ch in man_tree.get_children("")]
                    gm_dyncols.clear(); gm_dyncols.extend(new_dyn)
                    _man_build_tree_headers()
                    if rows:
                        man_tree.delete(*man_tree.get_children(""))
                        old_dyn_len = len(old)
                        for vals in rows:
                            base = [vals[0]]; old_dyn_vals = list(vals[1:1+old_dyn_len]); rest = list(vals[1+old_dyn_len:])
                            mapped = [old_dyn_vals[old.index(c)] for c in new_dyn]
                            man_tree.insert("", "end", values=base+mapped+rest)
                    _rebuild_manual_inputs(); _render_dynchips()
                return _cmd
            tb.Button(chip, text="✕", bootstyle=DANGER, width=2, command=_make_cmd()).pack(side=LEFT, padx=(2,6), pady=2)
    
    man_cap = tb.Labelframe(manual_frame, text="Captura de filas", padding=10)
    scroll_wrap = tb.Frame(man_cap)
    canvas = tk.Canvas(scroll_wrap, height=220, highlightthickness=0)
    vscroll = ttk.Scrollbar(scroll_wrap, orient="vertical", command=canvas.yview); canvas.configure(yscrollcommand=vscroll.set)
    canvas.pack(side=LEFT, fill=X, expand=True); vscroll.pack(side=RIGHT, fill=Y)
    bind_mousewheel(canvas, canvas.yview)
    
    inner = tb.Frame(canvas); inner_id = canvas.create_window((0,0), window=inner, anchor="nw")
    def _on_inner_config(event):
        """Auto-generated docstring for `_on_inner_config`."""
        canvas.configure(scrollregion=canvas.bbox("all"))
        try: canvas.itemconfig(inner_id, width=canvas.winfo_width())
        except Exception: pass
    inner.bind("<Configure>", _on_inner_config)
    def _on_canvas_config(event):
        """Auto-generated docstring for `_on_canvas_config`."""
        try: canvas.itemconfig(inner_id, width=event.width)
        except Exception: pass
    canvas.bind("<Configure>", _on_canvas_config)
    
    btns = tb.Frame(man_cap)
    
    man_prev = tb.Labelframe(manual_frame, text="Vista previa (manual)", padding=10)
    man_tv_wrap = tb.Frame(man_prev)
    man_tree = ttk.Treeview(man_tv_wrap, show="headings", height=10)
    man_vsb = ttk.Scrollbar(man_tv_wrap, orient="vertical", command=man_tree.yview); man_tree.configure(yscrollcommand=man_vsb.set)
    man_tree.pack(side=LEFT, fill=BOTH, expand=True); man_vsb.pack(side=RIGHT, fill=Y)
    bind_mousewheel(man_tree, man_tree.yview)
    man_actions = tb.Frame(manual_frame)
    
    def _man_build_tree_headers():
        """Auto-generated docstring for `_man_build_tree_headers`."""
        headers = ["NUMERO CASO DE PRUEBA", *gm_dyncols, "Caso de prueba", "¿Válido?", "PROCESAR"]
        man_tree.delete(*man_tree.get_children()); _tree_set_columns(man_tree, headers)
    
    def _rebuild_manual_inputs():
        """Auto-generated docstring for `_rebuild_manual_inputs`."""
        for w in inner.winfo_children(): w.destroy()
        row = 0
        tb.Label(inner, text="NUMERO CASO DE PRUEBA").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        case_no_var = tk.StringVar(value=f"CASO {gm_case_counter.get()}")
        tb.Label(inner, textvariable=case_no_var).grid(row=row, column=1, sticky="w")
        tb.Label(inner, text="Siguiente #").grid(row=row, column=2, sticky="e", padx=(12,4))
        try: sb = ttk.Spinbox(inner, from_=1, to=1000000, textvariable=gm_case_counter, width=8)
        except Exception: sb = tk.Spinbox(inner, from_=1, to=1000000, textvariable=gm_case_counter, width=8)
        sb.grid(row=row, column=3, sticky="w")
        # Botón superior agregar fila (visible)
        def _add_row():
            """Auto-generated docstring for `_add_row`."""
            missing = [c for c in gm_dyncols if not col_vars[c].get().strip()]
            if not case_txt.get().strip(): missing.append("Caso de prueba")
            if missing: messagebox.showwarning("Faltan datos", "Completa: " + ", ".join(missing)); return
            case_no = f"CASO {gm_case_counter.get()}"; gm_case_counter.set(gm_case_counter.get()+1)
            row_vals = [case_no] + [col_vars[c].get().strip() for c in gm_dyncols] + [case_txt.get().strip(), valid_var.get(), proc_var.get().strip()]
            man_tree.insert("", "end", values=row_vals); gm_status.set(f"Fila agregada ({case_no})")
            case_no_var.set(f"CASO {gm_case_counter.get()}"); case_txt.set(""); proc_var.set(""); val_combo.set("Sí")
            _renumber_cases(man_tree)
        tb.Button(inner, text="Agregar fila", bootstyle=PRIMARY, command=_add_row).grid(row=row, column=4, sticky="w", padx=(12,0))
        row += 1
    
        col_vars = {}
        for c in gm_dyncols:
            tb.Label(inner, text=c).grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
            v = tk.StringVar(value=""); col_vars[c] = v
            tb.Entry(inner, textvariable=v).grid(row=row, column=1, sticky="we", padx=(0,8), pady=4)
            row += 1
        inner.grid_columnconfigure(1, weight=1)
    
        tb.Label(inner, text="Caso de prueba").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        case_txt = tk.StringVar(value=""); tb.Entry(inner, textvariable=case_txt).grid(row=row, column=1, sticky="we", pady=4); row += 1
    
        tb.Label(inner, text="¿Válido?").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        valid_var = tk.StringVar(value="Sí"); val_combo = ttk.Combobox(inner, textvariable=valid_var, values=["Sí","No"], state="readonly", width=10)
        val_combo.grid(row=row, column=1, sticky="w", pady=4); row += 1
    
        tb.Label(inner, text="PROCESAR").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        proc_var = tk.StringVar(value=""); tb.Entry(inner, textvariable=proc_var, width=10).grid(row=row, column=1, sticky="w", pady=4); row += 1
    
        for w in btns.winfo_children(): w.destroy()
        def _clear_inputs():
            """Auto-generated docstring for `_clear_inputs`."""
            for c in gm_dyncols:
                try: col_vars[c].set("")
                except Exception: pass
            case_txt.set(""); val_combo.set("Sí"); proc_var.set("")
        tb.Button(btns, text="Agregar fila", bootstyle=PRIMARY, command=_add_row).pack(side=LEFT)
        tb.Button(btns, text="Limpiar entradas", bootstyle=SECONDARY, command=_clear_inputs).pack(side=LEFT, padx=(8,0))
    
    def _browse_import():
        """Auto-generated docstring for `_browse_import`."""
        path = filedialog.askopenfilename(filetypes=[("CSV o Excel","*.csv *.xlsx *.xls"),("Todos","*.*")])
        if not path: return
        imp_path.set(path); _load_import(path)
    
    def _load_import(path):
        """Auto-generated docstring for `_load_import`."""
        ext = os.path.splitext(path)[1].lower()
        rows = []; headers = []
        try:
            if ext == ".csv":
                headers, rows = _read_csv_any_encoding(path)
            elif ext in (".xlsx",".xls"):
                try: import openpyxl
                except Exception:
                    messagebox.showerror("XLSX no soportado", "Para importar XLSX/XLS instala 'openpyxl' o conviértelo a CSV."); return
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                ws = wb.active
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    vals = [("" if c is None else str(c)) for c in row]
                    if i == 0: headers = vals
                    else: rows.append(vals)
            else:
                messagebox.showwarning("Formato no soportado", "Selecciona un archivo .csv o .xlsx/.xls"); return
        except Exception as ex:
            messagebox.showerror("Error al leer archivo", f"No se pudo leer el archivo:\n{ex}"); return
    
        ok, msg = _headers_ok(headers)
        if not ok: messagebox.showwarning("Encabezados incompatibles", msg); return
    
        imp_tree.delete(*imp_tree.get_children()); _tree_set_columns(imp_tree, headers)
        for r in rows:
            if len(r) < len(headers): r = r + [""]*(len(headers)-len(r))
            elif len(r) > len(headers): r = r[:len(headers)]
            imp_tree.insert("", "end", values=r)
        _renumber_cases(imp_tree)
    
        _, dyn, _ = _split_headers(headers)
        gm_dyncols.clear(); gm_dyncols.extend(dyn)
        _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
        gm_status.set(f"Archivo cargado. Columnas dinámicas: {', '.join(dyn) if dyn else '(ninguna)'}")
    
    def _man_edit_selected():
        """Auto-generated docstring for `_man_edit_selected`."""
        sel = man_tree.selection()
        if not sel: messagebox.showinfo("Editar", "Selecciona una fila para editar."); return
        item = sel[0]; values = list(man_tree.item(item, 'values'))
        win = tk.Toplevel(root); win.title("Editar fila"); win.geometry("520x380")
        vars_map = []
        for i, h in enumerate(man_tree['columns']):
            v = tk.StringVar(value=values[i]); vars_map.append((h,v))
            fr = tb.Frame(win); fr.pack(fill=X, padx=10, pady=4)
            tb.Label(fr, text=h, width=24).pack(side=LEFT); tb.Entry(fr, textvariable=v).pack(side=LEFT, fill=X, expand=True)
        def _ok():
            """Auto-generated docstring for `_ok`."""
            new_vals = [v.get() for _,v in vars_map]; man_tree.item(item, values=new_vals); win.destroy()
        tb.Button(win, text="Guardar", bootstyle=PRIMARY, command=_ok).pack(side=RIGHT, padx=10, pady=10)
        tb.Button(win, text="Cancelar", bootstyle=SECONDARY, command=win.destroy).pack(side=RIGHT, pady=10)
    
    def _man_delete_selected():
        """Auto-generated docstring for `_man_delete_selected`."""
        sel = man_tree.selection()
        if not sel: return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {len(sel)} fila(s)?"): return
        for it in sel: man_tree.delete(it)
        _renumber_cases(man_tree)
    
    def _man_clear_all():
        """Auto-generated docstring for `_man_clear_all`."""
        if not man_tree.get_children(""): return
        if not messagebox.askyesno("Vaciar tabla", "¿Vaciar todas las filas capturadas?"): return
        man_tree.delete(*man_tree.get_children()); gm_case_counter.set(1)
    
    man_tree.bind("<Delete>", lambda e: (_man_delete_selected(), "break"))
    
    tb.Button(man_actions, text="Editar fila", bootstyle=SECONDARY, command=_man_edit_selected).pack(side=LEFT)
    tb.Button(man_actions, text="Eliminar fila", bootstyle=DANGER, command=_man_delete_selected).pack(side=LEFT, padx=(8,0))
    tb.Button(man_actions, text="Vaciar tabla", bootstyle=SECONDARY, command=_man_clear_all).pack(side=LEFT, padx=(8,0))
    
    def _show_mode():
        """Auto-generated docstring for `_show_mode`."""
        try:
            status_lbl.pack_forget()
            top.pack_forget(); gm_toolbar.pack_forget()
            import_frame.pack_forget(); imp_top.pack_forget(); imp_info.pack_forget(); imp_prev.pack_forget(); imp_tv_wrap.pack_forget(); imp_actions.pack_forget()
            manual_frame.pack_forget(); cols_bar.pack_forget(); chips_holder.pack_forget(); man_cap.pack_forget(); scroll_wrap.pack_forget(); btns.pack_forget(); man_prev.pack_forget(); man_tv_wrap.pack_forget(); man_actions.pack_forget()
        except Exception: pass
    
        mode = gm_mode.get()
        if mode not in ("import","manual"):
            gm_status.set("Elige cómo quieres trabajar (importar o captura manual).")
            status_lbl.pack(anchor="w", padx=6, pady=(6,0)); return
    
        top.pack(fill=X); gm_toolbar.pack(fill=X, pady=(6,0))
    
        if mode == "import":
            import_frame.pack(fill=BOTH, expand=True)
            imp_top.pack(fill=X); imp_info.pack(anchor="w", pady=(6,0))
            imp_prev.pack(fill=BOTH, expand=True, pady=(6,0)); imp_tv_wrap.pack(fill=BOTH, expand=True)
            imp_actions.pack(fill=X, pady=(6,0))
        else:
            manual_frame.pack(fill=BOTH, expand=True)
            cols_bar.pack(fill=X); chips_holder.pack(fill=X, pady=(8,0))
            man_cap.pack(fill=BOTH, expand=True, pady=(6,0))
            scroll_wrap.pack(fill=X); btns.pack(fill=X, pady=(6,0))
            man_prev.pack(fill=BOTH, expand=True, pady=(6,0)); man_tv_wrap.pack(fill=BOTH, expand=True)
            man_actions.pack(fill=X, pady=(6,0))
            _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
    
    def _load_dyncols_from_template():
        """Auto-generated docstring for `_load_dyncols_from_template`."""
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            headers, _rows = _read_csv_any_encoding(path)
            ok, msg = _headers_ok(headers)
            if not ok: messagebox.showwarning("Plantilla incompatible", msg); return
            _, dyn, _ = _split_headers(headers)
            gm_dyncols.clear(); gm_dyncols.extend(dyn)
            _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
            gm_status.set(f"Dinámicas cargadas: {', '.join(dyn) if dyn else '(ninguna)'}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo leer la plantilla:\n{ex}")
    

    _show_mode()

