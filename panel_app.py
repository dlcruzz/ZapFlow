import json
import random
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image as PILImage

import config
import icons as ic
from whatsapp_sender import enviar_para, read_contacts, validate_phone

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C = {
    "bg":      "#0f172a",
    "surface": "#1e293b",
    "card":    "#253047",
    "accent":  "#3b82f6",
    "success": "#10b981",
    "danger":  "#ef4444",
    "warning": "#f59e0b",
    "text":    "#f1f5f9",
    "subtext": "#94a3b8",
    "border":  "#334155",
}

_DEFAULT_MESSAGE = "Olá {nome}, tudo bem? 👋"


def _resource(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / relative


def _user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _style_treeview():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Z.Treeview",
        background=C["card"], foreground=C["text"],
        fieldbackground=C["card"], borderwidth=0,
        rowheight=38, font=("Segoe UI", 11))
    style.configure("Z.Treeview.Heading",
        background="#0f172a", foreground=C["subtext"],
        borderwidth=0, relief="flat", font=("Segoe UI", 11, "bold"))
    style.map("Z.Treeview",
        background=[("selected", C["accent"])],
        foreground=[("selected", "#ffffff")])
    style.configure("Z.Vertical.TScrollbar",
        background=C["surface"], troughcolor=C["bg"],
        borderwidth=0, arrowcolor=C["subtext"], relief="flat")


# ─────────────────────────────────────────────────────────────────────────────
# Janela de prévia estilo WhatsApp
# ─────────────────────────────────────────────────────────────────────────────

class PreviewWindow(ctk.CTkToplevel):
    def __init__(self, master, blocos: list[str], image_path: str | None = None):
        super().__init__(master)
        self.title("Pre-visualizacao da Mensagem")
        self.geometry("400x720")
        self.resizable(False, True)
        self.configure(fg_color="#0B141A")
        self.grab_set()

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#1F2C34", corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="ZapFlow Bot", font=("Segoe UI", 15, "bold"),
                     text_color="#E9EDEF").pack(side="left", padx=20, pady=16)
        ctk.CTkLabel(hdr, text="online", font=("Segoe UI", 11),
                     text_color="#00A884").pack(side="left", pady=16)

        # Chat area
        chat = ctk.CTkScrollableFrame(self, fg_color="#0B141A", corner_radius=0)
        chat.pack(fill="both", expand=True)
        chat.columnconfigure(0, weight=1)

        row = 0
        sample_name = "Joao"

        # Imagem
        if image_path and Path(image_path).exists():
            try:
                pil_img = PILImage.open(image_path).convert("RGBA")
                pil_img.thumbnail((260, 180))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                       size=pil_img.size)
                bubble = ctk.CTkFrame(chat, fg_color="#005C4B", corner_radius=12)
                bubble.grid(row=row, column=0, padx=(60, 14), pady=(16, 4), sticky="e")
                ctk.CTkLabel(bubble, image=ctk_img, text="").pack(padx=6, pady=6)
                row += 1
            except Exception:
                pass

        # Blocos de texto
        for bloco in blocos:
            try:
                text = bloco.format(nome=sample_name)
            except Exception:
                text = bloco
            bubble = ctk.CTkFrame(chat, fg_color="#005C4B", corner_radius=12)
            bubble.grid(row=row, column=0, padx=(60, 14), pady=4, sticky="e")
            bubble.columnconfigure(0, weight=1)
            ctk.CTkLabel(bubble, text=text, font=("Segoe UI", 12),
                         text_color="#E9EDEF", wraplength=230,
                         justify="left", anchor="w").grid(row=0, column=0,
                                                          padx=12, pady=(10, 4), sticky="w")
            ctk.CTkLabel(bubble, text=datetime.now().strftime("%H:%M"),
                         font=("Segoe UI", 9), text_color="#8696A0").grid(
                row=1, column=0, padx=10, pady=(0, 6), sticky="e")
            row += 1

        # Rodapé da prévia
        note = ctk.CTkFrame(self, fg_color="#1F2C34", corner_radius=0)
        note.pack(fill="x")
        ctk.CTkLabel(note,
                     text="Pre-visualizacao usando o nome 'Joao'.\n"
                          "No envio real, o nome de cada contato sera usado.",
                     font=("Segoe UI", 10), text_color="#8696A0",
                     justify="center").pack(pady=10)

        ctk.CTkButton(note, text="Fechar", command=self.destroy,
                      height=36, corner_radius=8,
                      fg_color=C["border"], hover_color="#475569",
                      font=("Segoe UI", 12)).pack(pady=(0, 12))


# ─────────────────────────────────────────────────────────────────────────────
# Card de estatística
# ─────────────────────────────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, color: str, **kw):
        super().__init__(master, corner_radius=14, fg_color=C["surface"], **kw)
        self.columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 11),
                     text_color=C["subtext"]).grid(row=0, column=0, sticky="w",
                                                   padx=16, pady=(14, 0))
        self._val = ctk.CTkLabel(self, text="0", font=("Segoe UI", 28, "bold"),
                                 text_color=color)
        self._val.grid(row=1, column=0, sticky="w", padx=16, pady=(2, 14))

    def set(self, value: str):
        self._val.configure(text=value)


# ─────────────────────────────────────────────────────────────────────────────
# Painel principal
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ZapFlow")
        self.geometry("1340x880")
        self.minsize(1100, 720)
        self.configure(fg_color=C["bg"])
        self._set_icon()

        self.contacts: list[dict] = []
        self.running = False
        self.stop_requested = False
        self.paused = False
        self.sent_count = 0
        self.failed_count = 0
        self.last_report = "Aguardando inicio..."
        self.block_widgets: list[tuple[ctk.CTkFrame, ctk.CTkTextbox]] = []
        self.image_path: str | None = None

        # Configuração de delay
        self.delay_mode     = tk.StringVar(value="aleatorio")
        self.delay_fixo_var = tk.StringVar(value="10")
        self.delay_min_var  = tk.StringVar(value="4")
        self.delay_max_var  = tk.StringVar(value="90")
        self.pause_min_var  = tk.StringVar(value="5")
        self.pause_max_var  = tk.StringVar(value="30")

        # Contador regressivo
        self.countdown_var  = tk.StringVar(value="")
        self._start_time    = 0.0
        self._estimated_total = 0
        self._countdown_id: str | None = None

        self.blocos = self._load_messages()

        _style_treeview()
        self._build_ui()
        self.load_contacts_from_csv()

    # ── Ícone ─────────────────────────────────────────────────────────────────

    def _set_icon(self):
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("zapflow.app")
        ico = _resource("img/zapflow.ico")
        png = _resource("img/zapflow.png")
        if ico.exists():
            self.iconbitmap(str(ico))
        elif png.exists():
            img = tk.PhotoImage(file=str(png))
            self.iconphoto(True, img)
            self._icon_ref = img

    # ── Mensagens persistidas ─────────────────────────────────────────────────

    def _messages_path(self) -> Path:
        return _user_data_dir() / "messages.json"

    def _load_messages(self) -> list[str]:
        path = self._messages_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return [_DEFAULT_MESSAGE]

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        self._build_header(root)

        tabs = ctk.CTkTabview(
            root, corner_radius=14, fg_color=C["surface"],
            segmented_button_fg_color=C["border"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color="#2563eb",
            segmented_button_unselected_color=C["border"],
            segmented_button_unselected_hover_color="#475569",
            text_color=C["text"],
        )
        tabs.grid(row=1, column=0, sticky="nsew", pady=(16, 0))

        t1 = tabs.add("Passo 1 — Mensagens")
        t2 = tabs.add("Passo 2 — Envio")

        t1.columnconfigure(0, weight=1)
        t1.rowconfigure(1, weight=1)
        self._build_messages_tab(t1)

        t2.columnconfigure(0, weight=1)
        t2.rowconfigure(1, weight=1)
        self._build_envio_tab(t2)

        self._build_footer(root)

    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=14, height=80)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(2, weight=1)
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, image=ic.bolt(26), text="").grid(row=0, column=0, padx=(20, 6), sticky="w")
        ctk.CTkLabel(hdr, text="ZapFlow", font=("Segoe UI", 24, "bold"),
                     text_color=C["accent"]).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(hdr, text="Automacao de Envio via WhatsApp",
                     font=("Segoe UI", 13), text_color=C["subtext"]).grid(
            row=0, column=2, padx=14, sticky="w")

        self.status_var = tk.StringVar(value="Pronto para iniciar")
        ctk.CTkLabel(hdr, textvariable=self.status_var,
                     font=("Segoe UI", 12, "bold"),
                     text_color=C["success"]).grid(row=0, column=3, padx=(0, 20), sticky="e")

        # Botão INICIAR + countdown sempre visíveis no header
        hdr_right = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_right.grid(row=0, column=4, padx=(0, 20), sticky="e")

        self.start_btn_hdr = ctk.CTkButton(
            hdr_right, text="INICIAR ENVIO", image=ic.play(20), compound="left",
            command=self.start_send_loop,
            height=48, width=200, corner_radius=10,
            font=("Segoe UI", 14, "bold"),
            fg_color=C["success"], hover_color="#059669",
        )
        self.start_btn_hdr.pack()

        self.countdown_label = ctk.CTkLabel(
            hdr_right, textvariable=self.countdown_var,
            font=("Segoe UI", 11, "bold"), text_color=C["warning"]
        )
        self.countdown_label.pack(pady=(2, 0))

    # ── Aba 1: Mensagens ──────────────────────────────────────────────────────

    def _build_messages_tab(self, parent):
        # Banner de instrução
        banner = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        banner.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        ctk.CTkLabel(banner,
                     text="Configure aqui o que sera enviado para cada contato.\n"
                          "Cada bloco e uma mensagem separada. Use {nome} para personalizar.",
                     font=("Segoe UI", 13), text_color=C["subtext"],
                     justify="left").pack(side="left", padx=16, pady=14)

        # Conteúdo em duas colunas
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Coluna esquerda: blocos de mensagem
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Mensagens", font=("Segoe UI", 14, "bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.blocks_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.blocks_scroll.grid(row=1, column=0, sticky="nsew")
        self.blocks_scroll.columnconfigure(0, weight=1)

        # Botões de ação dos blocos
        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        ctk.CTkButton(btns, text="Adicionar Mensagem", image=ic.add(), compound="left",
                      command=lambda: self._add_block(),
                      height=42, corner_radius=8, font=("Segoe UI", 12, "bold"),
                      fg_color=C["accent"], hover_color="#2563eb").pack(side="left", padx=(0, 8))

        ctk.CTkButton(btns, text="Salvar", image=ic.save(), compound="left",
                      command=self._save_messages,
                      height=42, corner_radius=8, font=("Segoe UI", 12, "bold"),
                      fg_color=C["success"], hover_color="#059669").pack(side="left")

        # Coluna direita: imagem + prévia
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        # Seção de imagem
        img_card = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        img_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        img_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(img_card, text="Imagem (opcional)",
                     font=("Segoe UI", 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(img_card,
                     text="A imagem sera enviada\nantes das mensagens de texto.",
                     font=("Segoe UI", 11), text_color=C["subtext"],
                     justify="left").grid(row=1, column=0, sticky="w", padx=16)

        self.img_thumb = ctk.CTkLabel(img_card, text="Nenhuma imagem\nselecionada",
                                      font=("Segoe UI", 11), text_color=C["subtext"],
                                      width=200, height=120)
        self.img_thumb.grid(row=2, column=0, padx=16, pady=10)

        ctk.CTkButton(img_card, text="Selecionar Imagem", image=ic.folder(), compound="left",
                      command=self._pick_image,
                      height=40, corner_radius=8, font=("Segoe UI", 12),
                      fg_color=C["accent"], hover_color="#2563eb").grid(
            row=3, column=0, padx=16, pady=(0, 6), sticky="ew")

        self.remove_img_btn = ctk.CTkButton(
            img_card, text="Remover Imagem", image=ic.trash(), compound="left",
            command=self._remove_image,
            height=38, corner_radius=8, font=("Segoe UI", 12),
            fg_color=C["border"], hover_color="#475569", state="disabled")
        self.remove_img_btn.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="ew")

        # Botão de prévia
        ctk.CTkButton(right, text="Ver Pre-visualizacao",
                      image=ic.export_icon(), compound="left",
                      command=self._show_preview,
                      height=48, corner_radius=10, font=("Segoe UI", 13, "bold"),
                      fg_color="#7c3aed", hover_color="#6d28d9").grid(
            row=1, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(right,
                     text="Veja como a mensagem\nvai chegar para o contato.",
                     font=("Segoe UI", 11), text_color=C["subtext"],
                     justify="center").grid(row=2, column=0)

        # Carregar blocos
        for bloco in self.blocos:
            self._add_block(bloco)

    def _add_block(self, text: str = ""):
        idx = len(self.block_widgets) + 1
        frame = ctk.CTkFrame(self.blocks_scroll, fg_color=C["surface"], corner_radius=10)
        frame.grid(row=idx - 1, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=f"Mensagem {idx}",
                     font=("Segoe UI", 12, "bold"), text_color=C["accent"],
                     width=110).grid(row=0, column=0, padx=(14, 8), pady=14, sticky="nw")

        # Coluna central: texto + botão {nome}
        col = ctk.CTkFrame(frame, fg_color="transparent")
        col.grid(row=0, column=1, padx=(0, 8), pady=12, sticky="ew")
        col.columnconfigure(0, weight=1)

        box = ctk.CTkTextbox(col, height=90, corner_radius=8,
                             fg_color=C["bg"], text_color=C["text"],
                             font=("Segoe UI", 12))
        box.grid(row=0, column=0, sticky="ew")
        placeholder = text if text else "Coloque seu texto aqui"
        box.insert("0.0", placeholder)

        ctk.CTkButton(
            col, text="Inserir {nome}",
            command=lambda b=box: b.insert(tk.INSERT, "{nome}"),
            height=28, corner_radius=6, font=("Segoe UI", 10),
            fg_color=C["border"], hover_color="#475569",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        def _remove(f=frame, b=box):
            self.block_widgets = [(fr, bx) for fr, bx in self.block_widgets if bx is not b]
            f.destroy()
            self._renumber_blocks()

        ctk.CTkButton(frame, text="", image=ic.close(14), command=_remove,
                      width=36, height=36, corner_radius=6,
                      fg_color=C["danger"], hover_color="#dc2626").grid(
            row=0, column=2, padx=(0, 12), pady=14, sticky="n")

        self.block_widgets.append((frame, box))

    def _renumber_blocks(self):
        for i, (frame, _) in enumerate(self.block_widgets):
            frame.grid(row=i, column=0, sticky="ew", pady=(0, 10))
            for child in frame.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("text").startswith("Mensagem"):
                    child.configure(text=f"Mensagem {i + 1}")

    def _save_messages(self):
        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso", "Adicione pelo menos uma mensagem antes de salvar.")
            return
        self.blocos = blocos
        self._messages_path().write_text(
            json.dumps(blocos, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log(f"Mensagens salvas: {len(blocos)} bloco(s).")
        messagebox.showinfo("Salvo", f"{len(blocos)} mensagem(ns) salva(s) com sucesso.")

    # ── Imagem ────────────────────────────────────────────────────────────────

    def _pick_image(self):
        path = filedialog.askopenfilename(
            title="Selecionar imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("Todos", "*.*")]
        )
        if not path:
            return
        self.image_path = path
        try:
            pil = PILImage.open(path).convert("RGBA")
            pil.thumbnail((200, 120))
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
            self.img_thumb.configure(image=ctk_img, text="")
            self.img_thumb._image = ctk_img  # manter referência
        except Exception:
            self.img_thumb.configure(image=None, text=Path(path).name)
        self.remove_img_btn.configure(state="normal")
        self.log(f"Imagem selecionada: {Path(path).name}")

    def _remove_image(self):
        self.image_path = None
        self.img_thumb.configure(image=None, text="Nenhuma imagem\nselecionada")
        self.remove_img_btn.configure(state="disabled")
        self.log("Imagem removida.")

    def _show_preview(self):
        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso", "Adicione pelo menos uma mensagem para visualizar.")
            return
        PreviewWindow(self, blocos, self.image_path)

    # ── Aba 2: Envio ──────────────────────────────────────────────────────────

    def _build_envio_tab(self, parent):
        # Banner de instrução
        banner = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        banner.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        ctk.CTkLabel(banner,
                     text="Carregue ou adicione os contatos e clique em Iniciar Envio para comecar.",
                     font=("Segoe UI", 13), text_color=C["subtext"]).pack(
            side="left", padx=16, pady=14)

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left_envio(body)
        self._build_right_envio(body)

    def _build_left_envio(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        # Formulário de adição
        form_card = ctk.CTkFrame(left, fg_color=C["surface"], corner_radius=14)
        form_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        form_card.columnconfigure(1, weight=1)
        form_card.columnconfigure(3, weight=1)

        ctk.CTkLabel(form_card, text="Adicionar contato",
                     font=("Segoe UI", 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, columnspan=5, sticky="w", padx=16, pady=(14, 8))

        ctk.CTkLabel(form_card, text="Nome:", font=("Segoe UI", 12),
                     text_color=C["subtext"]).grid(row=1, column=0, padx=(16, 6), pady=(0, 14))
        self.name_var = tk.StringVar()
        ne = ctk.CTkEntry(form_card, textvariable=self.name_var,
                          placeholder_text="Ex: Maria Silva", height=42,
                          corner_radius=8, font=("Segoe UI", 12))
        ne.grid(row=1, column=1, padx=(0, 16), pady=(0, 14), sticky="ew")
        ne.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkLabel(form_card, text="Telefone:", font=("Segoe UI", 12),
                     text_color=C["subtext"]).grid(row=1, column=2, padx=(0, 6), pady=(0, 14))
        self.phone_var = tk.StringVar()
        pe = ctk.CTkEntry(form_card, textvariable=self.phone_var,
                          placeholder_text="Ex: 11987654321", height=42,
                          corner_radius=8, font=("Segoe UI", 12))
        pe.grid(row=1, column=3, padx=(0, 16), pady=(0, 14), sticky="ew")
        pe.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkButton(form_card, text="Adicionar", image=ic.add(), compound="left",
                      command=self.add_contact,
                      height=42, corner_radius=8, font=("Segoe UI", 12, "bold"),
                      fg_color=C["accent"], hover_color="#2563eb").grid(
            row=1, column=4, padx=(0, 16), pady=(0, 14))

        # Ações CSV
        csv_bar = ctk.CTkFrame(left, fg_color="transparent")
        csv_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        def _btn(text, cmd, img):
            return ctk.CTkButton(csv_bar, text=text, image=img, compound="left",
                                 command=cmd, height=40, corner_radius=8,
                                 font=("Segoe UI", 12), fg_color=C["border"],
                                 hover_color="#475569")

        _btn("Carregar CSV", self.load_contacts_from_csv, ic.folder()).pack(side="left", padx=(0, 6))
        _btn("Salvar CSV",   self.save_contacts_to_csv,   ic.save()  ).pack(side="left", padx=6)
        _btn("Remover",      self.remove_selected,         ic.trash() ).pack(side="left", padx=6)
        _btn("Exportar",     self.export_report,           ic.chart() ).pack(side="left", padx=6)

        # Tabela
        table_card = ctk.CTkFrame(left, fg_color=C["surface"], corner_radius=14)
        table_card.grid(row=2, column=0, sticky="nsew")
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(1, weight=1)

        ctk.CTkLabel(table_card, text="Lista de Contatos",
                     font=("Segoe UI", 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        tree_host = tk.Frame(table_card, bg=C["surface"], bd=0, highlightthickness=0)
        tree_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tree_host.columnconfigure(0, weight=1)
        tree_host.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_host,
                                 columns=("nome", "telefone", "status"),
                                 show="headings", style="Z.Treeview")
        self.tree.heading("nome",     text="  Nome")
        self.tree.heading("telefone", text="  Telefone")
        self.tree.heading("status",   text="Status")
        self.tree.column("nome",     width=260, anchor="w",      stretch=True)
        self.tree.column("telefone", width=200, anchor="w",      stretch=True)
        self.tree.column("status",   width=130, anchor="center", stretch=False)
        self.tree.tag_configure("enviado",  foreground=C["success"])
        self.tree.tag_configure("falha",    foreground=C["danger"])
        self.tree.tag_configure("enviando", foreground=C["warning"])
        self.tree.tag_configure("pendente", foreground=C["subtext"])

        vsb = ttk.Scrollbar(tree_host, orient="vertical", command=self.tree.yview,
                            style="Z.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    def _build_right_envio(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        # ── Configuração de tempo ─────────────────────────────────────────────
        delay_card = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        delay_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        delay_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(delay_card, text="Configuracao de Tempo",
                     font=("Segoe UI", 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        # Toggle Fixo / Aleatório
        toggle = ctk.CTkFrame(delay_card, fg_color="transparent")
        toggle.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        ctk.CTkRadioButton(toggle, text="Fixo", variable=self.delay_mode, value="fixo",
                           command=self._on_delay_mode_change,
                           font=("Segoe UI", 12)).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(toggle, text="Aleatorio", variable=self.delay_mode, value="aleatorio",
                           command=self._on_delay_mode_change,
                           font=("Segoe UI", 12)).pack(side="left")

        # Frame modo Fixo
        self._delay_fixo_frame = ctk.CTkFrame(delay_card, fg_color="transparent")
        self._delay_fixo_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        ctk.CTkLabel(self._delay_fixo_frame, text="Aguardar",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")
        ctk.CTkEntry(self._delay_fixo_frame, textvariable=self.delay_fixo_var,
                     width=70, height=34, corner_radius=6,
                     font=("Segoe UI", 12)).pack(side="left", padx=8)
        ctk.CTkLabel(self._delay_fixo_frame, text="seg entre mensagens",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")

        # Frame modo Aleatório
        self._delay_rand_frame = ctk.CTkFrame(delay_card, fg_color="transparent")
        self._delay_rand_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        ctk.CTkLabel(self._delay_rand_frame, text="Entre",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")
        ctk.CTkEntry(self._delay_rand_frame, textvariable=self.delay_min_var,
                     width=65, height=34, corner_radius=6,
                     font=("Segoe UI", 12)).pack(side="left", padx=6)
        ctk.CTkLabel(self._delay_rand_frame, text="e",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")
        ctk.CTkEntry(self._delay_rand_frame, textvariable=self.delay_max_var,
                     width=65, height=34, corner_radius=6,
                     font=("Segoe UI", 12)).pack(side="left", padx=6)
        ctk.CTkLabel(self._delay_rand_frame, text="seg (aleatorio)",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")

        # Pausa entre contatos
        pause_row = ctk.CTkFrame(delay_card, fg_color="transparent")
        pause_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 14))
        ctk.CTkLabel(pause_row, text="Pausa entre contatos:",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")
        ctk.CTkEntry(pause_row, textvariable=self.pause_min_var,
                     width=60, height=34, corner_radius=6,
                     font=("Segoe UI", 12)).pack(side="left", padx=6)
        ctk.CTkLabel(pause_row, text="a",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")
        ctk.CTkEntry(pause_row, textvariable=self.pause_max_var,
                     width=60, height=34, corner_radius=6,
                     font=("Segoe UI", 12)).pack(side="left", padx=6)
        ctk.CTkLabel(pause_row, text="seg",
                     font=("Segoe UI", 12), text_color=C["subtext"]).pack(side="left")

        self._on_delay_mode_change()  # aplica visibilidade inicial

        # Cards de estatísticas (2x2)
        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.card_total   = StatCard(cards, "Total",    C["accent"])
        self.card_sent    = StatCard(cards, "Enviados", C["success"])
        self.card_failed  = StatCard(cards, "Falhas",   C["danger"])
        self.card_pending = StatCard(cards, "Pendentes",C["warning"])
        self.card_total  .grid(row=0, column=0, padx=(0, 6), pady=(0, 6), sticky="ew")
        self.card_sent   .grid(row=0, column=1, padx=(6, 0), pady=(0, 6), sticky="ew")
        self.card_failed .grid(row=1, column=0, padx=(0, 6), pady=(6, 0), sticky="ew")
        self.card_pending.grid(row=1, column=1, padx=(6, 0), pady=(6, 0), sticky="ew")

        # Progresso
        prog = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        prog.grid(row=2, column=0, sticky="ew", pady=(12, 12))
        prog.columnconfigure(0, weight=1)

        self.summary_var = tk.StringVar(value="0 / 0 concluidos")
        ctk.CTkLabel(prog, textvariable=self.summary_var,
                     font=("Segoe UI", 13, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        self.progress_bar = ctk.CTkProgressBar(prog, height=16, corner_radius=8,
                                               fg_color=C["border"],
                                               progress_color=C["accent"])
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

        # Botões de controle
        ctrl = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        ctrl.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        ctrl.columnconfigure(0, weight=1)

        ctk.CTkLabel(ctrl, text="Controle de Envio",
                     font=("Segoe UI", 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        ctk.CTkButton(ctrl, text="INICIAR ENVIO", image=ic.play(22), compound="left",
                      command=self.start_send_loop,
                      height=58, corner_radius=10, font=("Segoe UI", 16, "bold"),
                      fg_color=C["success"], hover_color="#059669").grid(
            row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        sub = ctk.CTkFrame(ctrl, fg_color="transparent")
        sub.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        sub.columnconfigure(0, weight=1)
        sub.columnconfigure(1, weight=1)

        self.pause_btn = ctk.CTkButton(sub, text="Pausar", image=ic.pause(), compound="left",
                                       command=self.pause_send_loop,
                                       height=42, corner_radius=8,
                                       font=("Segoe UI", 12, "bold"),
                                       fg_color=C["warning"], hover_color="#d97706")
        self.pause_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(sub, text="Parar", image=ic.stop(), compound="left",
                      command=self.stop_send_loop,
                      height=42, corner_radius=8, font=("Segoe UI", 12, "bold"),
                      fg_color=C["danger"], hover_color="#dc2626").grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        # Log
        log_card = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        log_card.grid(row=4, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        log_hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(log_hdr, text="Log de Atividade",
                     font=("Segoe UI", 13, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(log_hdr, text="Limpar", image=ic.close(13), compound="left",
                      command=self.clear_log,
                      width=80, height=28, corner_radius=6,
                      fg_color=C["border"], hover_color="#475569",
                      font=("Segoe UI", 10)).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_card, font=("Consolas", 10), corner_radius=8,
                                      fg_color=C["bg"], text_color=C["text"],
                                      state="disabled", wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

    def _build_footer(self, parent):
        footer = ctk.CTkFrame(parent, fg_color="transparent", height=28)
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        footer.grid_propagate(False)

        ctk.CTkLabel(footer, text="Desenvolvido por ",
                     font=("Segoe UI", 10), text_color=C["subtext"]).grid(
            row=0, column=0, sticky="e")

        link = ctk.CTkLabel(footer, text="ZINKRA",
                            font=("Segoe UI", 10, "bold"),
                            text_color=C["accent"], cursor="hand2")
        link.grid(row=0, column=1, sticky="w")
        link.bind("<Button-1>", lambda _: webbrowser.open("https://www.zinkra.com.br"))
        link.bind("<Enter>",    lambda _: link.configure(text_color="#60a5fa"))
        link.bind("<Leave>",    lambda _: link.configure(text_color=C["accent"]))

    # ── Delay e tempo ────────────────────────────────────────────────────────

    def _on_delay_mode_change(self):
        if self.delay_mode.get() == "fixo":
            self._delay_rand_frame.grid_remove()
            self._delay_fixo_frame.grid()
        else:
            self._delay_fixo_frame.grid_remove()
            self._delay_rand_frame.grid()

    def _get_block_delay(self) -> float:
        try:
            if self.delay_mode.get() == "fixo":
                return max(1.0, float(self.delay_fixo_var.get()))
            mn = max(1.0, float(self.delay_min_var.get()))
            mx = max(mn, float(self.delay_max_var.get()))
            return random.uniform(mn, mx)
        except ValueError:
            return 10.0

    def _get_pause_delay(self) -> float:
        try:
            mn = max(1.0, float(self.pause_min_var.get()))
            mx = max(mn, float(self.pause_max_var.get()))
            return random.uniform(mn, mx)
        except ValueError:
            return random.uniform(5.0, 30.0)

    def _estimate_total_seconds(self, n_contacts: int, n_blocks: int) -> int:
        try:
            if self.delay_mode.get() == "fixo":
                avg_block = float(self.delay_fixo_var.get())
            else:
                mn = float(self.delay_min_var.get())
                mx = float(self.delay_max_var.get())
                avg_block = (mn + mx) / 2
            avg_pause = (float(self.pause_min_var.get()) + float(self.pause_max_var.get())) / 2
            overhead = 8  # abertura do chat + foco na janela
            return int(n_contacts * (overhead + n_blocks * avg_block + avg_pause))
        except ValueError:
            return 0

    @staticmethod
    def _format_time(seconds: int) -> str:
        if seconds <= 0:
            return "0 seg"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h {m}min {s}seg"
        if m > 0:
            return f"{m}min {s}seg"
        return f"{s}seg"

    def _tick_countdown(self):
        if not self.running:
            self.countdown_var.set("")
            return
        elapsed    = int(time.time() - self._start_time)
        remaining  = max(0, self._estimated_total - elapsed)
        self.countdown_var.set(f"Restante: {self._format_time(remaining)}")
        self._countdown_id = self.after(1000, self._tick_countdown)

    # ── Thread-safe helpers ───────────────────────────────────────────────────

    def _log_safe(self, msg: str):
        self.after(0, lambda: self.log(msg))

    def _set_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))

    # ── Ações de contato ──────────────────────────────────────────────────────

    def add_contact(self):
        nome     = self.name_var.get().strip()
        telefone = self.phone_var.get().strip()
        if not nome or not telefone:
            messagebox.showwarning("Aviso", "Preencha nome e telefone antes de adicionar.")
            return
        try:
            telefone = validate_phone(telefone)
        except Exception as exc:
            messagebox.showerror("Erro", f"Telefone invalido: {exc}")
            return
        self.contacts.append({"nome": nome, "telefone": telefone, "status": "Pendente"})
        self.refresh_table()
        self.name_var.set("")
        self.phone_var.set("")
        self.log(f"Contato adicionado: {nome} ({telefone})")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um contato para remover.")
            return
        values = self.tree.item(sel[0])["values"]
        nome = values[0] if values else ""
        if messagebox.askyesno("Confirmar", f"Remover {nome} da lista?"):
            for idx, c in enumerate(self.contacts):
                if c["nome"] == values[0] and c["telefone"] == values[1]:
                    del self.contacts[idx]
                    break
            self.refresh_table()
            self.log(f"Contato removido: {nome}")

    def load_contacts_from_csv(self):
        try:
            contatos = read_contacts(config.CSV_FILE)
        except FileNotFoundError:
            messagebox.showwarning("Arquivo nao encontrado",
                                   f"Nao foi encontrado: {config.CSV_FILE}")
            self.contacts = []
            self.refresh_table()
            return
        self.contacts = [{"nome": c["nome"], "telefone": c["telefone"], "status": "Pendente"}
                         for c in contatos]
        self.refresh_table()
        self.log(f"Carregados {len(self.contacts)} contatos do CSV.")

    def save_contacts_to_csv(self):
        path = Path(config.CSV_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write("nome,telefone\n")
            for c in self.contacts:
                f.write(f"{c['nome']},{c['telefone']}\n")
        self.log(f"CSV salvo em {path}.")
        messagebox.showinfo("Sucesso", "Lista salva no CSV.")

    def export_report(self):
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        rpath = Path(f"relatorio_{ts}.txt")
        total   = len(self.contacts)
        sent    = sum(1 for c in self.contacts if c.get("status") == "Enviado")
        failed  = sum(1 for c in self.contacts if c.get("status") == "Falha")
        pending = total - sent - failed
        lines = [
            "=" * 65,
            f"  RELATORIO DE ENVIO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "=" * 65,
            f"  Total: {total}   Enviados: {sent}   Falhas: {failed}   Pendentes: {pending}",
            "-" * 65,
            f"  {'Nome':<30} {'Telefone':<20} Status",
            "-" * 65,
        ]
        for c in self.contacts:
            lines.append(f"  {c['nome']:<30} {c['telefone']:<20} {c.get('status','Pendente')}")
        lines.append("=" * 65)
        rpath.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"Relatorio exportado: {rpath}")
        messagebox.showinfo("Relatorio", f"Arquivo criado: {rpath}")

    # ── Tabela ────────────────────────────────────────────────────────────────

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.contacts:
            status = item.get("status", "Pendente")
            self.tree.insert("", "end",
                             values=(item["nome"], item["telefone"], status),
                             tags=(status.lower(),))
        total             = len(self.contacts)
        self.sent_count   = sum(1 for c in self.contacts if c.get("status") == "Enviado")
        self.failed_count = sum(1 for c in self.contacts if c.get("status") == "Falha")
        pending           = total - self.sent_count - self.failed_count

        self.card_total  .set(str(total))
        self.card_sent   .set(str(self.sent_count))
        self.card_failed .set(str(self.failed_count))
        self.card_pending.set(str(pending))

        ratio = (self.sent_count + self.failed_count) / total if total else 0
        self.progress_bar.set(ratio)
        self.summary_var.set(f"{self.sent_count + self.failed_count} / {total} concluidos")
        self.last_report = (
            f"Total={total} | Enviados={self.sent_count} | "
            f"Falhas={self.failed_count} | Pendentes={pending}"
        )

    # ── Log ───────────────────────────────────────────────────────────────────

    def log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", tk.END)
        self.log_box.configure(state="disabled")

    # ── Controle de envio ─────────────────────────────────────────────────────

    def start_send_loop(self):
        if self.running:
            return
        if not self.contacts:
            messagebox.showwarning("Aviso", "Carregue ou adicione contatos antes de iniciar.")
            return
        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso",
                                   "Configure pelo menos uma mensagem no Passo 1 — Mensagens.")
            return
        self.blocos = blocos
        self.running          = True
        self.stop_requested   = False
        self.paused           = False
        self._start_time      = time.time()
        self._estimated_total = self._estimate_total_seconds(len(self.contacts), len(blocos))

        self.pause_btn.configure(text="Pausar", image=ic.pause())
        self.status_var.set("Enviando mensagens...")
        estimativa = self._format_time(self._estimated_total)
        self.countdown_var.set(f"Estimativa: {estimativa}")
        self.log(f"Iniciando envio — {len(self.blocos)} mensagem(ns), "
                 f"{len(self.contacts)} contato(s). Tempo estimado: {estimativa}.")
        self._tick_countdown()
        threading.Thread(target=self._send_all, daemon=True).start()

    def pause_send_loop(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="Retomar", image=ic.play())
            self._set_status("Pausado")
            self._log_safe("Envio pausado.")
        else:
            self.pause_btn.configure(text="Pausar", image=ic.pause())
            self._set_status("Enviando mensagens...")
            self._log_safe("Envio retomado.")

    def stop_send_loop(self):
        self.stop_requested = True
        self._set_status("Parando envio...")
        self._log_safe("Solicitacao de parada enviada.")

    def _send_all(self):
        blocos     = list(self.blocos)
        image_path = self.image_path
        total      = len(self.contacts)

        for index, item in enumerate(self.contacts):
            if self.stop_requested:
                break
            while self.paused and not self.stop_requested:
                time.sleep(0.5)
            if self.stop_requested:
                break

            nome     = item["nome"]
            telefone = item["telefone"]
            self._update_item_status(index, "Enviando")
            self._log_safe(f"[{index + 1}/{total}] Enviando para {nome}...")

            try:
                d_min = d_max = float(self.delay_fixo_var.get()) if self.delay_mode.get() == "fixo" \
                    else (float(self.delay_min_var.get()), float(self.delay_max_var.get()))[0]
                d_max = d_min if self.delay_mode.get() == "fixo" else float(self.delay_max_var.get())
                enviar_para(nome, telefone, blocos, image_path,
                            delay_min=d_min, delay_max=d_max)
                self._update_item_status(index, "Enviado")
                self._log_safe(f"[{index + 1}/{total}] Concluido: {nome}")
            except Exception as exc:
                self._update_item_status(index, "Falha")
                self._log_safe(f"[{index + 1}/{total}] Erro com {nome}: {exc}")

            # Pausa entre contatos (exceto após o último)
            if index < total - 1 and not self.stop_requested:
                pausa = self._get_pause_delay()
                self._log_safe(f"Aguardando {pausa:.0f}s antes do proximo contato...")
                time.sleep(pausa)

        self.running = False
        self._set_status("Concluido" if not self.stop_requested else "Parado pelo usuario")
        self._log_safe("Processo finalizado.")
        self.after(0, lambda: messagebox.showinfo("Resumo final", self.last_report))

    def _update_item_status(self, index: int, status: str):
        if index < len(self.contacts):
            self.contacts[index]["status"] = status
            self.after(0, self.refresh_table)


if __name__ == "__main__":
    app = WhatsAppPanel()
    app.mainloop()
