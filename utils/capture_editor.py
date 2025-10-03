# capture_editor.py (Imagen arriba 100% con Zoom, Scroll y atajos aislados al canvas)
from __future__ import annotations
import os, math, tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from dataclasses import dataclass
from typing import Dict, Tuple, List
from PIL import Image, ImageTk, ImageDraw, ImageFont

try:
    import ttkbootstrap as tb
    _USE_TTKB = True
except Exception:
    _USE_TTKB = False

@dataclass
class EditorMeta:
    descripcion: str = ""
    consideraciones: str = ""
    observaciones: str = ""

@dataclass
class DrawAction:
    kind: str                 # 'rect', 'line', 'free', 'text'
    coords: List[Tuple[int,int]]   # almacenado en coords de **imagen**
    color: Tuple[int,int,int] = (255,0,0)
    width: int = 4
    text: str = ""
    font_size: int = 18

class CaptureEditor(tk.Toplevel):
    def __init__(self, master, image_path:str, meta:EditorMeta):
        super().__init__(master)
        self.title("Editor de captura")
        self.geometry("1910x1000")
        self.minsize(980, 600)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

        # Datos
        self.image_path = image_path
        self.meta = meta
        self._base_img = Image.open(self.image_path).convert("RGBA")
        self._disp_img = None
        self._tk_img = None

        # Acciones
        self.actions: List[DrawAction] = []
        self._drawing = False
        self._start_xy_img = None
        self._last_xy_img = None
        self._temp_canvas_item = None
        self._crop_bbox_img = None

        # Estado de estilo
        self.current_tool = tk.StringVar(value="rect")
        self.stroke_color = (255, 0, 0)
        self.stroke_width = tk.IntVar(value=4)
        self.font_size = tk.IntVar(value=20)

        # Zoom & Scroll
        self.zoom_mode = tk.StringVar(value="fit")  # 'fit' por defecto; 'manual' al hacer zoom
        self.scale = 1.0
        self._min_scale = 0.1
        self._max_scale = 4.0

        # Layout: Toolbar (fila 0) | Preview (fila 1) | Inputs (fila 2)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        self._build_toolbar(self)
        self._build_preview(self)
        self._build_inputs(self)

        # Redibuja al redimensionar si está en modo "fit"
        self.bind("<Configure>", lambda e: (self._refresh_preview() if self.zoom_mode.get()=="fit" else None))
        self.after(50, self._refresh_preview)

    # ---------- UI ----------

    def _toggle_fullscreen(self):
        try:
            current = bool(self.attributes("-fullscreen"))
        except Exception:
            current = False
        self.attributes("-fullscreen", not current)

    def _minimize_window(self):
        try:
            self.iconify()
        except Exception:
            pass

    def _build_toolbar(self, parent):
        bar = (tb.Frame(parent, padding=6) if _USE_TTKB else ttk.Frame(parent, padding=6))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(99, weight=1)

        def add_tool(text, value, col):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.current_tool).grid(row=0, column=col, padx=3)

        add_tool("Rect", "rect", 0)
        add_tool("Flecha", "line", 1)
        add_tool("Lápiz", "free", 2)
        add_tool("Texto", "text", 3)
        add_tool("Recortar", "crop", 4)

        ttk.Label(bar, text=" Grosor:").grid(row=0, column=10, padx=(12,3))
        ttk.Spinbox(bar, from_=1, to=30, textvariable=self.stroke_width, width=5).grid(row=0, column=11)

        ttk.Label(bar, text=" Tamaño texto:").grid(row=0, column=12, padx=(12,3))
        ttk.Spinbox(bar, from_=8, to=72, textvariable=self.font_size, width=5).grid(row=0, column=13)

        def choose_color():
            c = colorchooser.askcolor(color="#%02x%02x%02x" % self.stroke_color, title="Elige color")
            if c and c[0]:
                r,g,b = map(int, c[0]); self.stroke_color = (r,g,b)
        ttk.Button(bar, text="Color...", command=choose_color).grid(row=0, column=14, padx=6)

        # Zoom
        ttk.Label(bar, text=" ").grid(row=0, column=20, padx=4)
        ttk.Button(bar, text="Ajustar", command=self._zoom_fit).grid(row=0, column=21, padx=2)
        ttk.Button(bar, text="100%", command=self._zoom_100).grid(row=0, column=22, padx=2)
        ttk.Button(bar, text="−", width=3, command=lambda: self._zoom_step(0.9)).grid(row=0, column=23, padx=2)
        ttk.Button(bar, text="+", width=3, command=lambda: self._zoom_step(1.1)).grid(row=0, column=24, padx=2)
        self.lbl_zoom = ttk.Label(bar, text="100%"); self.lbl_zoom.grid(row=0, column=25, padx=(8,0))


        ttk.Label(bar, text="").grid(row=0, column=90, sticky="ew")
        ttk.Button(bar, text="Minimizar", command=self._minimize_window).grid(row=0, column=91, padx=4)
        ttk.Button(bar, text="Pantalla completa (F11)", command=self._toggle_fullscreen).grid(row=0, column=92, padx=4)
        ttk.Button(bar, text="Cerrar", command=self.on_cancel).grid(row=0, column=93, padx=4)
        ttk.Label(bar, text="").grid(row=0, column=99, sticky="ew")
        ttk.Button(bar, text="Deshacer (Ctrl+Z)", command=self.on_undo).grid(row=0, column=100, padx=3)
        ttk.Button(bar, text="Reset dibujo", command=self.on_reset_drawings).grid(row=0, column=101, padx=3)
        ttk.Button(bar, text="Guardar (Ctrl+S)", command=self.on_save).grid(row=0, column=102, padx=3)
        ttk.Button(bar, text="Cancelar (Esc)", command=self.on_cancel).grid(row=0, column=103, padx=3)
        
        # Teclas de ventana que no molestan al escribir en Text
        self.bind("<Escape>", lambda e: self.on_cancel())
        self.bind("<Control-s>", self._on_ctrl_s_window); self.bind("<Control-S>", self._on_ctrl_s_window)

    def _build_preview(self, parent):
        wrap = ttk.Frame(parent)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)
        self.preview_wrap = wrap

        # Canvas con scrollbars
        self.canvas = tk.Canvas(wrap, background="#222", highlightthickness=0, cursor="cross")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)

        # Atajos SOLO en canvas (evita dispararse mientras escribes)
        for key, tool in [("r","rect"), ("l","line"), ("p","free"), ("t","text"), ("c","crop"),
                          ("R","rect"), ("L","line"), ("P","free"), ("T","text"), ("C","crop")]:
            self.canvas.bind(f"<KeyPress-{key}>", lambda e, t=tool: self._set_tool(t))
        self.canvas.bind("<Control-z>", lambda e: (self.on_undo(), "break"))
        self.canvas.bind("<Control-Z>", lambda e: (self.on_undo(), "break"))

        # Zoom con Ctrl+Rueda
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        # Linux opcional
        self.canvas.bind("<Control-Button-4>", lambda e: self._zoom_step(1.1))
        self.canvas.bind("<Control-Button-5>", lambda e: self._zoom_step(0.9))

        # Paneo con botón medio
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_move)

        # Dibujo
        self.canvas.bind("<ButtonPress-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

        # Scroll con rueda (sin Ctrl)
        self.canvas.bind("<MouseWheel>", self._on_wheel)              # Windows/macOS: vertical
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel_shift)  # Windows/macOS: horizontal

        # Linux/X11 (rueda arriba/abajo)
        self.canvas.bind("<Button-4>",  lambda e: self._wheel_linux(-1, False))
        self.canvas.bind("<Button-5>",  lambda e: self._wheel_linux( 1, False))
        self.canvas.bind("<Shift-Button-4>", lambda e: self._wheel_linux(-1, True))
        self.canvas.bind("<Shift-Button-5>", lambda e: self._wheel_linux( 1, True))


        self.canvas.focus_set()

    def _build_inputs(self, parent):
        right = (tb.Labelframe(parent, text="Metadatos de la captura", padding=8) if _USE_TTKB
                 else ttk.LabelFrame(parent, text="Metadatos de la captura", padding=8))
        right.grid(row=2, column=0, sticky="ew", padx=(6,6), pady=(4,8))
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Descripción").grid(row=0, column=0, sticky="w")
        self.txt_desc = tk.Text(right, height=3, wrap="word", undo=True); self.txt_desc.grid(row=1, column=0, sticky="ew", pady=(0,8))

        ttk.Label(right, text="Consideraciones").grid(row=2, column=0, sticky="w")
        self.txt_cons = tk.Text(right, height=3, wrap="word", undo=True); self.txt_cons.grid(row=3, column=0, sticky="ew", pady=(0,8))

        ttk.Label(right, text="Observaciones").grid(row=4, column=0, sticky="w")
        self.txt_obs = tk.Text(right, height=3, wrap="word", undo=True); self.txt_obs.grid(row=5, column=0, sticky="ew", pady=(0,0))

        # preload
        self.txt_desc.insert("1.0", self.meta.descripcion or "")
        self.txt_cons.insert("1.0", self.meta.consideraciones or "")
        self.txt_obs.insert("1.0", self.meta.observaciones or "")

        tips = ("Canvas: R/L/P/T/C · Ctrl+Wheel=Zoom · Ctrl+Z (deshacer) · Botón medio para pan")
        ttk.Label(right, text=tips, foreground="#666").grid(row=6, column=0, sticky="w", pady=(8,0))

    # ---------- Teclas ----------

    def _on_wheel(self, e):
        # Si vienes con Ctrl, deja que el handler de zoom lo maneje
        if e.state & 0x0004:  # Ctrl
            return
        move = -1 if e.delta > 0 else 1   # Windows/macOS: delta>0 rueda arriba
        self.canvas.yview_scroll(move, "units")
        return "break"

    def _on_wheel_shift(self, e):
        if e.state & 0x0004:  # Ctrl
            return
        move = -1 if e.delta > 0 else 1
        self.canvas.xview_scroll(move, "units")
        return "break"

    def _wheel_linux(self, step, horizontal=False):
        # step: -1 arriba/izq, 1 abajo/der
        if horizontal:
            self.canvas.xview_scroll(step, "units")
        else:
            self.canvas.yview_scroll(step, "units")
        return "break"



    def _on_ctrl_s_window(self, e):
        # No sobrescribas Ctrl+S si el foco está en Text/Entry
        w = self.focus_get()
        if isinstance(w, (tk.Text, tk.Entry)):
            return
        self.on_save()
        return "break"

    def _set_tool(self, t):
        if self.focus_get() == self.canvas:
            self.current_tool.set(t)

    # ---------- Zoom & Scroll ----------
    def _zoom_fit(self):
        self.zoom_mode.set("fit")
        self._refresh_preview()

    def _zoom_100(self):
        self.zoom_mode.set("manual")
        self.scale = 1.0
        self._refresh_preview()

    def _on_ctrl_wheel(self, e):
        factor = 1.1 if e.delta > 0 else 0.9
        self._zoom_step(factor)
        return "break"

    def _zoom_step(self, factor):
        self.zoom_mode.set("manual")
        new_scale = max(self._min_scale, min(self._max_scale, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-6:
            return
        # zoom respecto al centro visible
        c_x = self.canvas.canvasx(self.canvas.winfo_width()//2)
        c_y = self.canvas.canvasy(self.canvas.winfo_height()//2)
        img_cx, img_cy = self._to_img(c_x, c_y)
        self.scale = new_scale
        self._refresh_preview()
        # re-centrar
        nx, ny = self._to_disp(img_cx, img_cy)
        self.canvas.xview_moveto(max(0, (nx - self.canvas.winfo_width()//2) / max(1, self._disp_img.width)))
        self.canvas.yview_moveto(max(0, (ny - self.canvas.winfo_height()//2) / max(1, self._disp_img.height)))

    def _pan_start(self, e):
        self.canvas.scan_mark(e.x, e.y)

    def _pan_move(self, e):
        self.canvas.scan_dragto(e.x, e.y, gain=1)

    # ---------- Escalado ----------
    def _compute_scale(self):
        img_w, img_h = self._base_img.size
        avail_w = max(1, self.preview_wrap.winfo_width() - self.vbar.winfo_width())
        avail_h = max(1, self.preview_wrap.winfo_height() - self.hbar.winfo_height())
        if self.zoom_mode.get() == "manual":
            return self.scale
        s = min(avail_w / img_w, avail_h / img_h)
        s = max(min(s, self._max_scale), self._min_scale)
        return s

    def _refresh_preview(self):
        s = self._compute_scale()
        self.scale = s
        disp_w = max(1, int(self._base_img.width * self.scale))
        disp_h = max(1, int(self._base_img.height * self.scale))
        self._disp_img = self._base_img.resize((disp_w, disp_h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(self._disp_img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img, tags=("IMG",))
        self.canvas.config(scrollregion=(0,0,disp_w,disp_h))

        # overlays
        if self._crop_bbox_img:
            x1,y1,x2,y2 = self._crop_bbox_img
            self._draw_rect_preview(self._to_disp(x1,y1) + self._to_disp(x2,y2), outline="#00bcd4", dash=(4,2))
        self._repaint_actions_preview()

        self.lbl_zoom.config(text=f"{int(round(self.scale*100))}%")

    # Mapeos imagen<->display
    def _to_disp(self, x:int, y:int) -> Tuple[int,int]:
        return (int(round(x*self.scale)), int(round(y*self.scale)))

    def _to_img(self, dx:int, dy:int) -> Tuple[int,int]:
        return (int(round(dx/self.scale)), int(round(dy/self.scale)))

    # ---------- Dibujo ----------
    def _on_down(self, event):
        self.canvas.focus_set()
        self._drawing = True
        dx, dy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self._start_xy_img = self._to_img(int(dx), int(dy))
        self._last_xy_img = self._start_xy_img
        tool = self.current_tool.get()

        if tool == "text":
            self._create_text_item_at(self._start_xy_img); self._drawing = False; return
        elif tool == "crop":
            self._crop_bbox_img = (*self._start_xy_img, *self._start_xy_img); return

        if tool == "rect":
            x1,y1 = self._to_disp(*self._start_xy_img)
            self._temp_canvas_item = self._draw_rect_preview((x1,y1,x1,y1))
        elif tool == "line":
            x1,y1 = self._to_disp(*self._start_xy_img)
            self._temp_canvas_item = self.canvas.create_line(x1,y1,x1,y1,
                fill=self._rgb_to_hex(self.stroke_color), width=self.stroke_width.get(), arrow=tk.LAST)
        elif tool == "free":
            x1,y1 = self._to_disp(*self._start_xy_img)
            self._temp_canvas_item = self.canvas.create_line(x1,y1,x1,y1,
                fill=self._rgb_to_hex(self.stroke_color), width=self.stroke_width.get(), capstyle=tk.ROUND, smooth=True)

    def _on_drag(self, event):
        if not self._drawing or self._start_xy_img is None: return
        dx, dy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        tool = self.current_tool.get()
        x_img, y_img = self._to_img(int(dx), int(dy))

        if tool == "crop":
            x1,y1,_,_ = self._crop_bbox_img
            self._crop_bbox_img = (x1,y1,x_img,y_img)
            self._refresh_preview()
            return

        if self._temp_canvas_item is None: return
        x1,y1 = self._to_disp(*self._start_xy_img)
        x2,y2 = self._to_disp(x_img, y_img)
        if tool in ("rect","line"):
            self.canvas.coords(self._temp_canvas_item, x1,y1,x2,y2)
        elif tool == "free":
            self.canvas.coords(self._temp_canvas_item, *self.canvas.coords(self._temp_canvas_item), x2,y2)
        self._last_xy_img = (x_img, y_img)

    def _on_up(self, event):
        if not self._drawing: return
        self._drawing = False
        dx, dy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x2, y2 = self._to_img(int(dx), int(dy))
        tool = self.current_tool.get()

        if tool == "crop":
            return

        if self._temp_canvas_item is None: return
        x1,y1 = self._start_xy_img
        if abs(x2-x1) < 2 and abs(y2-y1) < 2:
            self.canvas.delete(self._temp_canvas_item); self._temp_canvas_item = None; return

        if tool == "rect":
            action = DrawAction(kind="rect", coords=[(x1,y1), (x2,y2)],
                                color=self.stroke_color, width=self.stroke_width.get())
        elif tool == "line":
            action = DrawAction(kind="line", coords=[(x1,y1), (x2,y2)],
                                color=self.stroke_color, width=self.stroke_width.get())
        elif tool == "free":
            coords = self.canvas.coords(self._temp_canvas_item)
            pts = []
            for i in range(0, len(coords), 2):
                ddx, ddy = int(coords[i]), int(coords[i+1])
                pts.append(self._to_img(ddx,ddy))
            action = DrawAction(kind="free", coords=pts, color=self.stroke_color, width=self.stroke_width.get())
        else:
            action = None

        if action: self.actions.append(action)
        self._temp_canvas_item = None

    def _on_double_click(self, event):
        if self.current_tool.get() == "text":
            dx, dy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self._create_text_item_at(self._to_img(int(dx),int(dy)))

    # ---------- Texto ----------
    def _create_text_item_at(self, xy_img):
        win = tk.Toplevel(self); win.title("Texto"); win.transient(self); win.grab_set()
        ttk.Label(win, text="Contenido del texto:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        entry = tk.Text(win, width=40, height=4, undo=True); entry.grid(row=1, column=0, padx=8, pady=(0,8))
        def ok():
            content = entry.get("1.0","end").strip("\n")
            if content:
                action = DrawAction(kind="text", coords=[(int(xy_img[0]), int(xy_img[1]))],
                                    color=self.stroke_color, width=self.stroke_width.get(),
                                    text=content, font_size=self.font_size.get())
                self.actions.append(action)
                TX,TY = self._to_disp(*xy_img)
                self.canvas.create_text(TX,TY, text=content, fill=self._rgb_to_hex(self.stroke_color),
                                        font=("Segoe UI", self.font_size.get(), "bold"), anchor="nw")
            win.destroy()
        ttk.Button(win, text="OK", command=ok).grid(row=2, column=0, padx=8, pady=8, sticky="e")
        win.wait_window()

    # ---------- Acciones ----------
    def on_undo(self):
        if not self.actions: return
        self.actions.pop()
        self._refresh_preview()

    def on_reset_drawings(self):
        if messagebox.askyesno("Confirmar", "¿Eliminar todas las anotaciones?"):
            self.actions.clear(); self._crop_bbox_img = None
            self._refresh_preview()

    # ---------- Guardar / Cancelar ----------
    def on_save(self):
        self.meta.descripcion = self.txt_desc.get("1.0","end").strip("\n")
        self.meta.consideraciones = self.txt_cons.get("1.0","end").strip("\n")
        self.meta.observaciones = self.txt_obs.get("1.0","end").strip("\n")

        base = self._base_img.copy()
        if self._crop_bbox_img:
            x1,y1,x2,y2 = self._crop_bbox_img
            x1,x2 = sorted([int(x1),int(x2)]); y1,y2 = sorted([int(y1),int(y2)])
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(base.size[0], x2); y2 = min(base.size[1], y2)
            if x2 > x1 and y2 > y1:
                base = base.crop((x1,y1,x2,y2))

        draw = ImageDraw.Draw(base)
        try:
            font = ImageFont.truetype("segoeui.ttf", size=max(12, self.font_size.get()))
        except Exception:
            font = ImageFont.load_default()

        for a in self.actions:
            if a.kind == "rect":
                draw.rectangle([a.coords[0], a.coords[1]], outline=a.color, width=a.width)
            elif a.kind == "line":
                (x1,y1),(x2,y2) = a.coords
                draw.line([x1,y1,x2,y2], fill=a.color, width=a.width)
                self._draw_arrow_head(draw, (x1,y1), (x2,y2), a.color, a.width)
            elif a.kind == "free":
                if len(a.coords) >= 2:
                    draw.line(a.coords, fill=a.color, width=a.width, joint="curve")
            elif a.kind == "text":
                (tx,ty) = a.coords[0]
                draw.text((tx,ty), a.text, fill=a.color, font=font, stroke_width=1, stroke_fill=(0,0,0))

        root, ext = os.path.splitext(self.image_path)
        out_path = f"{root}_edit.png"
        base.save(out_path)
        self.result = (out_path, {
            "descripcion": self.meta.descripcion,
            "consideraciones": self.meta.consideraciones,
            "observaciones": self.meta.observaciones
        })
        self.destroy()

    def on_cancel(self):
        self.result = (self.image_path, {
            "descripcion": self.meta.descripcion,
            "consideraciones": self.meta.consideraciones,
            "observaciones": self.meta.observaciones
        })
        self.destroy()

    # ---------- Helpers ----------
    def _repaint_actions_preview(self):
        for a in self.actions:
            if a.kind == "rect":
                (x1,y1),(x2,y2) = a.coords
                X1,Y1 = self._to_disp(x1,y1); X2,Y2 = self._to_disp(x2,y2)
                self._draw_rect_preview((X1,Y1,X2,Y2))
            elif a.kind == "line":
                (x1,y1),(x2,y2) = a.coords
                X1,Y1 = self._to_disp(x1,y1); X2,Y2 = self._to_disp(x2,y2)
                self.canvas.create_line(X1,Y1,X2,Y2, fill=self._rgb_to_hex(a.color), width=a.width, arrow=tk.LAST)
            elif a.kind == "free":
                flat = []
                for (x,y) in a.coords:
                    X,Y = self._to_disp(x,y); flat += [X,Y]
                if len(flat) >= 4:
                    self.canvas.create_line(*flat, fill=self._rgb_to_hex(a.color), width=a.width,
                                            capstyle=tk.ROUND, smooth=True)
            elif a.kind == "text":
                (tx,ty) = a.coords[0]
                TX,TY = self._to_disp(tx,ty)
                self.canvas.create_text(TX,TY, text=a.text, fill=self._rgb_to_hex(a.color),
                                        font=("Segoe UI", a.font_size, "bold"), anchor="nw")

    def _draw_rect_preview(self, rect, outline=None, dash=None):
        return self.canvas.create_rectangle(*rect, outline=outline or self._rgb_to_hex(self.stroke_color),
                                            width=self.stroke_width.get(), dash=dash)

    def _draw_arrow_head(self, draw:ImageDraw.ImageDraw, p1, p2, color, width):
        x1,y1 = p1; x2,y2 = p2
        angle = math.atan2(y2 - y1, x2 - x1)
        length = max(8, 3*width)
        alpha = math.pi / 6
        p_left = (x2 - length*math.cos(angle - alpha), y2 - length*math.sin(angle - alpha))
        p_right = (x2 - length*math.cos(angle + alpha), y2 - length*math.sin(angle + alpha))
        draw.polygon([p2, p_left, p_right], fill=color)

    def _rgb_to_hex(self, rgb): return "#%02x%02x%02x" % rgb

def open_capture_editor(image_path:str, meta_dict:Dict[str,str]):
    root = tk._default_root; created = False
    if root is None:
        root = (tb.Window(themename="flatly") if _USE_TTKB else tk.Tk())
        root.withdraw(); created = True

    meta = EditorMeta(
        descripcion=meta_dict.get("descripcion",""),
        consideraciones=meta_dict.get("consideraciones",""),
        observaciones=meta_dict.get("observaciones",""),
    )
    editor = CaptureEditor(root, image_path=image_path, meta=meta)
    editor.wait_window()

    if created:
        root.destroy()
    return editor.result
