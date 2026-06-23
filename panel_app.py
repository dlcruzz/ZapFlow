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
from anti_ban import DailyStats, parse_spin
from instagram_sender import (InstagramDMError, InstagramLoginError,
                               InstagramUserNotFound,
                               abrir_app_instagram, enviar_instagram)
from theme import T, F, STATUS
from whatsapp_sender import (InvalidWhatsAppNumberError, enviar_para,
                             read_contacts, validate_phone)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _resource(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / relative


def _user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# Componentes reutilizáveis
# ─────────────────────────────────────────────────────────────────────────────

class Tooltip:
    """Tooltip elegante que aparece ao passar o mouse."""
    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text   = text
        self._win: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event=None):
        if self._win:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, background="#1A1F24", foreground=T["text_2"],
                 font=F["label_sm"], padx=10, pady=6,
                 relief="flat", borderwidth=0).pack()

    def _hide(self, event=None):
        if self._win:
            self._win.destroy()
            self._win = None


class SidebarBtn(ctk.CTkFrame):
    """Botão de navegação da sidebar com estado ativo e hover."""
    def __init__(self, master, text: str, image, command, **kw):
        super().__init__(master, fg_color="transparent", corner_radius=T["r_btn"],
                         cursor="hand2", **kw)
        self._cmd    = command
        self._active = False

        self._img_lbl = ctk.CTkLabel(self, image=image, text="", width=22)
        self._img_lbl.pack(side="left", padx=(12, 8), pady=10)

        self._txt_lbl = ctk.CTkLabel(self, text=text, font=F["body"],
                                      text_color=T["text_2"], anchor="w")
        self._txt_lbl.pack(side="left", fill="x", expand=True, pady=10)

        for w in (self, self._img_lbl, self._txt_lbl):
            w.bind("<Button-1>", lambda _: self._cmd())
            w.bind("<Enter>",    lambda _: self._on_hover(True))
            w.bind("<Leave>",    lambda _: self._on_hover(False))

    def _on_hover(self, on: bool):
        if self._active:
            return
        self.configure(fg_color=T["bg_hover"] if on else "transparent")

    def set_active(self, active: bool):
        self._active = active
        self.configure(fg_color=T["accent_dim"] if active else "transparent")
        self._txt_lbl.configure(
            text_color=T["accent"] if active else T["text_2"],
            font=(F["body"][0], F["body"][1], "bold") if active else F["body"]
        )


class StatPill(ctk.CTkFrame):
    """Pill de estatística no header."""
    def __init__(self, master, label: str, color: str, **kw):
        super().__init__(master, fg_color=T["bg_elevated"], corner_radius=T["r_pill"], **kw)
        self._lbl = ctk.CTkLabel(self, text=f"{label}: 0", font=F["label"],
                                  text_color=color)
        self._lbl.pack(padx=12, pady=4)

    def set(self, label: str, value: str):
        self._lbl.configure(text=f"{label}: {value}")


class Badge(ctk.CTkLabel):
    """Badge colorido de status."""
    def __init__(self, master, text: str, **kw):
        color = STATUS.get(text, T["text_3"])
        super().__init__(master, text=text, font=F["label_sm"],
                         text_color=color,
                         fg_color=T["bg_elevated"],
                         corner_radius=T["r_pill"],
                         padx=8, pady=2, **kw)


def _section_header(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=title, font=F["heading"], text_color=T["text_1"]).pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(f, text=subtitle, font=F["body_sm"], text_color=T["text_3"]).pack(anchor="w")
    return f


def _card(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=T["bg_surface"], corner_radius=T["r_card"], **kw)


def _divider(parent):
    ctk.CTkFrame(parent, fg_color=T["border"], height=1).pack(fill="x", pady=12)


def _style_tree():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Z.Treeview",
        background=T["bg_elevated"], foreground=T["text_1"],
        fieldbackground=T["bg_elevated"], borderwidth=0,
        rowheight=36, font=F["body"])
    s.configure("Z.Treeview.Heading",
        background=T["bg_base"], foreground=T["text_3"],
        borderwidth=0, relief="flat", font=F["label"])
    s.map("Z.Treeview",
        background=[("selected", T["accent_dim"])],
        foreground=[("selected", T["accent"])])
    s.configure("Z.Vertical.TScrollbar",
        background=T["bg_surface"], troughcolor=T["bg_base"],
        borderwidth=0, arrowcolor=T["text_3"], relief="flat")


# ─────────────────────────────────────────────────────────────────────────────
# Janela de prévia WhatsApp
# ─────────────────────────────────────────────────────────────────────────────

class PreviewWindow(ctk.CTkToplevel):
    def __init__(self, master, blocos: list[str], image_path: str | None = None):
        super().__init__(master)
        self.title("Prévia da Mensagem")
        self.geometry("400x700")
        self.resizable(False, True)
        self.configure(fg_color="#0B141A")
        self.grab_set()

        hdr = ctk.CTkFrame(self, fg_color="#1F2C34", corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="ZapFlow Bot", font=F["subhead"],
                     text_color="#E9EDEF").pack(side="left", padx=20, pady=16)
        ctk.CTkLabel(hdr, text="online", font=F["body_sm"],
                     text_color="#00A884").pack(side="left", pady=16)

        chat = ctk.CTkScrollableFrame(self, fg_color="#0B141A", corner_radius=0)
        chat.pack(fill="both", expand=True)
        chat.columnconfigure(0, weight=1)

        row = 0
        sample = "Joao"

        if image_path and Path(image_path).exists():
            try:
                pil = PILImage.open(image_path).convert("RGBA")
                pil.thumbnail((260, 180))
                cimg = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
                b = ctk.CTkFrame(chat, fg_color="#005C4B", corner_radius=12)
                b.grid(row=row, column=0, padx=(60, 14), pady=(16, 4), sticky="e")
                ctk.CTkLabel(b, image=cimg, text="").pack(padx=6, pady=6)
                row += 1
            except Exception:
                pass

        for bloco in blocos:
            try:
                text = bloco.format(nome=sample)
            except Exception:
                text = bloco
            b = ctk.CTkFrame(chat, fg_color="#005C4B", corner_radius=12)
            b.grid(row=row, column=0, padx=(60, 14), pady=4, sticky="e")
            b.columnconfigure(0, weight=1)
            ctk.CTkLabel(b, text=text, font=F["body"], text_color="#E9EDEF",
                         wraplength=230, justify="left", anchor="w").grid(
                row=0, column=0, padx=12, pady=(10, 4), sticky="w")
            ctk.CTkLabel(b, text=datetime.now().strftime("%H:%M"),
                         font=F["label_sm"], text_color="#8696A0").grid(
                row=1, column=0, padx=10, pady=(0, 6), sticky="e")
            row += 1

        note = ctk.CTkFrame(self, fg_color="#1F2C34", corner_radius=0)
        note.pack(fill="x")
        ctk.CTkLabel(note,
                     text="Prévia com o nome 'Joao'. No envio real,\n"
                          "o nome de cada contato será usado.",
                     font=F["label_sm"], text_color="#8696A0",
                     justify="center").pack(pady=8)
        ctk.CTkButton(note, text="Fechar", command=self.destroy,
                      height=34, corner_radius=T["r_btn"],
                      fg_color=T["bg_elevated"], hover_color=T["bg_hover"],
                      font=F["body"]).pack(pady=(0, 10))


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard final
# ─────────────────────────────────────────────────────────────────────────────

class FinalDashboard(ctk.CTkToplevel):
    def __init__(self, master, contacts: list[dict], export_fn):
        super().__init__(master)
        self.title("Resultado do Envio")
        self.geometry("800x600")
        self.minsize(640, 480)
        self.configure(fg_color=T["bg_base"])
        self.grab_set()

        sent   = [c for c in contacts if c.get("status") == "Enviado"]
        failed = [c for c in contacts if c.get("status") == "Falha"]
        total  = len(contacts)
        ok     = not failed

        hdr = ctk.CTkFrame(self, fg_color=T["accent"] if ok else T["warning"],
                           corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,
                     text="Envio concluído!" if ok else "Concluído com falhas",
                     font=F["heading"], text_color="#fff").pack(
            side="left", padx=24, pady=18)

        # KPI cards
        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.pack(fill="x", padx=24, pady=16)
        for i in range(3):
            kpi_row.columnconfigure(i, weight=1)

        def _kpi(col, lbl, val, color):
            f = _card(kpi_row)
            f.grid(row=0, column=col, padx=6, sticky="ew")
            ctk.CTkLabel(f, text=lbl, font=F["label"],
                         text_color=T["text_3"]).pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(f, text=str(val), font=("Consolas", 28, "bold"),
                         text_color=color).pack(anchor="w", padx=16, pady=(4, 12))

        _kpi(0, "Enviados",  len(sent),  T["success"])
        _kpi(1, "Falhas",    len(failed), T["danger"])
        _kpi(2, "Total",     total,       T["info"])

        ctk.CTkLabel(self, text="Detalhe por contato",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=24, pady=(0, 8))

        tf = tk.Frame(self, bg=T["bg_base"])
        tf.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        _style_tree()
        tree = ttk.Treeview(tf, columns=("nome", "telefone", "status"),
                            show="headings", style="Z.Treeview")
        tree.heading("nome",     text="  Nome")
        tree.heading("telefone", text="  Telefone")
        tree.heading("status",   text="Status")
        tree.column("nome",     width=280, anchor="w")
        tree.column("telefone", width=200, anchor="w")
        tree.column("status",   width=140, anchor="center")
        tree.tag_configure("enviado", foreground=T["success"])
        tree.tag_configure("falha",   foreground=T["danger"])

        vsb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview,
                            style="Z.Vertical.TScrollbar")
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        for c in contacts:
            st = c.get("status", "—")
            tree.insert("", "end", values=(c["nome"], c["telefone"], st),
                        tags=(st.lower(),))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkButton(btns, text="Exportar Relatório", image=ic.export_icon(),
                      compound="left", command=export_fn,
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).pack(
            side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="Fechar", command=self.destroy,
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["bg_elevated"],
                      hover_color=T["bg_hover"]).pack(side="left")


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding
# ─────────────────────────────────────────────────────────────────────────────

class OnboardingOverlay(ctk.CTkFrame):
    STEPS = [
        ("Bem-vindo ao ZapFlow!",
         "Automatize seus envios no WhatsApp de forma inteligente e segura.\n"
         "Vamos te mostrar como funciona em 4 passos rápidos.",
         "Próximo →"),
        ("Passo 1 — Mensagens",
         "Na aba Mensagens, escreva o que será enviado.\n"
         "Use {nome} para personalizar e [opção1/opção2] para variar o texto automaticamente.\n"
         "Você pode adicionar quantos blocos quiser — cada bloco = uma mensagem separada.",
         "Próximo →"),
        ("Passo 2 — Contatos",
         "Na aba Contatos, adicione quem vai receber.\n"
         "Cole a coluna de Nomes e a coluna de Telefones direto do Excel.\n"
         "Ou carregue um arquivo CSV com um clique.",
         "Próximo →"),
        ("Passo 3 — Proteção Anti-Bloqueio",
         "Configure o delay entre mensagens e ative as proteções:\n"
         "• Digitação humana letra por letra (já ativo)\n"
         "• Horário humanizado • Limite diário • Modo Aquecimento\n"
         "Isso reduz drasticamente o risco de bloqueio.",
         "Próximo →"),
        ("Tudo pronto!",
         "Clique em INICIAR ENVIO no topo da tela a qualquer momento.\n"
         "Você pode acompanhar o progresso em tempo real na aba Monitoramento.\n\n"
         "Bom envio! ⚡",
         "Começar"),
    ]

    def __init__(self, master, on_done):
        super().__init__(master, fg_color=T["bg_base"] + "EE", corner_radius=0)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._on_done = on_done
        self._step    = 0

        # Card central
        card = _card(self)
        card.place(relx=0.5, rely=0.5, anchor="center", width=520)

        self._title_lbl = ctk.CTkLabel(card, text="", font=F["heading"],
                                        text_color=T["text_1"])
        self._title_lbl.pack(padx=32, pady=(32, 12), anchor="w")

        self._body_lbl = ctk.CTkLabel(card, text="", font=F["body"],
                                       text_color=T["text_2"],
                                       wraplength=440, justify="left")
        self._body_lbl.pack(padx=32, pady=(0, 24), anchor="w")

        # Indicadores de passo
        self._dots_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._dots_frame.pack(padx=32, pady=(0, 16), anchor="w")
        self._dots = []
        for _ in self.STEPS:
            d = ctk.CTkFrame(self._dots_frame, fg_color=T["text_3"],
                             corner_radius=99, width=8, height=8)
            d.pack(side="left", padx=3)
            d.pack_propagate(False)
            self._dots.append(d)

        self._btn = ctk.CTkButton(card, text="", command=self._next,
                                   height=42, corner_radius=T["r_btn"],
                                   font=F["subhead"],
                                   fg_color=T["accent"],
                                   hover_color=T["accent_hover"])
        self._btn.pack(padx=32, pady=(0, 32), fill="x")

        self._render()

    def _render(self):
        title, body, btn_text = self.STEPS[self._step]
        self._title_lbl.configure(text=title)
        self._body_lbl.configure(text=body)
        self._btn.configure(text=btn_text)
        for i, d in enumerate(self._dots):
            d.configure(fg_color=T["accent"] if i == self._step else T["text_3"])

    def _next(self):
        self._step += 1
        if self._step >= len(self.STEPS):
            self.place_forget()
            self.destroy()
            self._on_done()
        else:
            self._render()


# ─────────────────────────────────────────────────────────────────────────────
# App principal
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppPanel(ctk.CTk):
    PAGES = ["mensagens", "contatos", "tempo", "antibloqueio", "monitoramento", "instagram"]

    def __init__(self):
        super().__init__()
        self.title("ZapFlow")
        self.geometry("1340x860")
        self.minsize(1100, 720)
        self.configure(fg_color=T["bg_base"])
        self._set_icon()
        _style_tree()

        # ── Estado da aplicação ───────────────────────────────────────────────
        self.contacts:   list[dict] = []
        self.running     = False
        self.stop_requested = False
        self.paused      = False
        self.sent_count  = 0
        self.failed_count= 0
        self.last_report = "Aguardando início..."
        self.block_widgets: list[tuple[ctk.CTkFrame, ctk.CTkTextbox]] = []
        self.image_path: str | None = None

        # Mensagens
        self.blocos = self._load_messages()

        # Delay
        self.delay_mode      = tk.StringVar(value="aleatorio")
        self.delay_fixo_var  = tk.StringVar(value="10")
        self.delay_min_var   = tk.StringVar(value="4")
        self.delay_max_var   = tk.StringVar(value="90")
        self.pause_min_var   = tk.StringVar(value="5")
        self.pause_max_var   = tk.StringVar(value="30")

        # Anti-ban
        self.daily_limit_enabled   = tk.BooleanVar(value=False)
        self.daily_limit_var       = tk.StringVar(value="50")
        self.warmup_enabled        = tk.BooleanVar(value=False)
        self.human_hours_enabled   = tk.BooleanVar(value=False)
        self.hours_start_var       = tk.StringVar(value="08:00")
        self.hours_end_var         = tk.StringVar(value="20:00")
        self.typing_profile_var    = tk.StringVar(value="Aleatorio")
        self.session_split_enabled = tk.BooleanVar(value=False)
        self.session_size_var      = tk.StringVar(value="30")
        self.session_pause_var     = tk.StringVar(value="30")
        self._consecutive_errors   = 0
        self._daily_stats          = DailyStats(_user_data_dir())

        # Countdown
        self.countdown_var     = tk.StringVar(value="")
        self._start_time       = 0.0
        self._estimated_total  = 0
        self._countdown_id     = None

        # Live status
        self.live_contact_var  = tk.StringVar(value="—")
        self.live_msg_var      = tk.StringVar(value="—")
        self.live_next_var     = tk.StringVar(value="—")
        self.warmup_status_var = tk.StringVar(value=self._daily_stats.status_line())

        # Instagram
        self.ig_running    = False
        self.ig_stop       = False
        self.ig_status_var = tk.StringVar(value="Pronto")

        # Entrada em massa
        self.name_var  = tk.StringVar()
        self.phone_var = tk.StringVar()

        # Status geral
        self.status_var = tk.StringVar(value="Pronto para iniciar")

        self._build_ui()
        self._navigate("mensagens")
        self._auto_load_csv()
        self._check_onboarding()

    # ──────────────────────────────────────────────────────────────────────────
    # Ícone
    # ──────────────────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────────────────
    # Mensagens persistidas
    # ──────────────────────────────────────────────────────────────────────────

    def _messages_path(self) -> Path:
        return _user_data_dir() / "messages.json"

    def _load_messages(self) -> list[str]:
        p = self._messages_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return [config.BLOCOS[0] if config.BLOCOS else "Olá {nome}, tudo bem?"]

    # ──────────────────────────────────────────────────────────────────────────
    # Layout raiz
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_content()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=T["bg_surface"], corner_radius=0,
                           height=T["topbar_h"])
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(1, weight=1)

        # Logo
        logo_f = ctk.CTkFrame(bar, fg_color="transparent")
        logo_f.grid(row=0, column=0, padx=20, sticky="w")
        ctk.CTkLabel(logo_f, image=ic.bolt(22), text="").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(logo_f, text="ZapFlow", font=F["title"],
                     text_color=T["accent"]).pack(side="left")

        # Status + pills
        mid = ctk.CTkFrame(bar, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="ew", padx=16)

        self.status_lbl = ctk.CTkLabel(mid, textvariable=self.status_var,
                                        font=F["label"], text_color=T["text_3"])
        self.status_lbl.pack(side="left", padx=(0, 16))

        self.pill_total   = StatPill(mid, "Total",    T["info"])
        self.pill_sent    = StatPill(mid, "Enviados",  T["success"])
        self.pill_failed  = StatPill(mid, "Falhas",    T["danger"])
        self.pill_pending = StatPill(mid, "Pendentes", T["warning"])
        for p in (self.pill_total, self.pill_sent, self.pill_failed, self.pill_pending):
            p.pack(side="left", padx=4)

        # Countdown
        ctk.CTkLabel(bar, textvariable=self.countdown_var,
                     font=("Consolas", 11, "bold"), text_color=T["warning"]).grid(
            row=0, column=2, padx=12, sticky="e")

        # INICIAR ENVIO
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=3, padx=(0, 16), sticky="e")

        self.start_btn = ctk.CTkButton(right, text="INICIAR ENVIO",
                                        image=ic.play(18), compound="left",
                                        command=self.start_send_loop,
                                        height=40, width=180, corner_radius=T["r_btn"],
                                        font=F["subhead"],
                                        fg_color=T["accent"],
                                        hover_color=T["accent_hover"])
        self.start_btn.pack(side="left", padx=(0, 8))

        self.pause_btn = ctk.CTkButton(right, text="Pausar",
                                        image=ic.pause(16), compound="left",
                                        command=self.pause_send_loop,
                                        height=40, width=100, corner_radius=T["r_btn"],
                                        font=F["body"],
                                        fg_color=T["warning"], hover_color="#D4870F")
        self.pause_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(right, text="Parar",
                      image=ic.stop(16), compound="left",
                      command=self.stop_send_loop,
                      height=40, width=90, corner_radius=T["r_btn"],
                      font=F["body"],
                      fg_color=T["danger"], hover_color="#D93535").pack(side="left")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=T["bg_surface"], corner_radius=0,
                          width=T["sidebar_w"])
        sb.grid(row=1, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.columnconfigure(0, weight=1)

        ctk.CTkFrame(sb, fg_color=T["border"], height=1).pack(fill="x")

        NAV = [
            ("mensagens",     "Mensagens",      ic.msg(18)),
            ("contatos",      "Contatos",        ic.person(18)),
            ("tempo",         "Tempo & Delay",   ic.clock(18)),
            ("antibloqueio",  "Anti-Bloqueio",   ic.shield(18)),
            ("monitoramento", "Monitoramento",   ic.chart(18)),
            ("instagram",     "Instagram DM",    ic.camera(18)),
        ]

        self._nav_btns: dict[str, SidebarBtn] = {}
        for key, label, img in NAV:
            btn = SidebarBtn(sb, text=label, image=img,
                             command=lambda k=key: self._navigate(k))
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[key] = btn

        # Separador + ajuda
        ctk.CTkFrame(sb, fg_color=T["border"], height=1).pack(fill="x", pady=8)

        help_btn = SidebarBtn(sb, text="Tutorial", image=ic.help_icon(18),
                              command=self._show_onboarding)
        help_btn.pack(fill="x", padx=8, pady=2, side="bottom")

        Tooltip(help_btn, "Ver tutorial de uso do ZapFlow")

        # ZINKRA
        ctk.CTkFrame(sb, fg_color=T["border"], height=1).pack(fill="x", side="bottom")
        footer = ctk.CTkFrame(sb, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=8)
        ctk.CTkLabel(footer, text="por ", font=F["label_sm"],
                     text_color=T["text_3"]).pack(side="left", padx=(16, 0))
        link = ctk.CTkLabel(footer, text="ZINKRA", font=(F["label_sm"][0], F["label_sm"][1], "bold"),
                            text_color=T["accent"], cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda _: webbrowser.open("https://www.zinkra.com.br"))

    def _build_content(self):
        self._content = ctk.CTkFrame(self, fg_color=T["bg_base"], corner_radius=0)
        self._content.grid(row=1, column=1, sticky="nsew")
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        self._pages: dict[str, ctk.CTkScrollableFrame | ctk.CTkFrame] = {}
        builders = {
            "mensagens":     self._build_page_messages,
            "contatos":      self._build_page_contacts,
            "tempo":         self._build_page_timing,
            "antibloqueio":  self._build_page_antiblock,
            "monitoramento": self._build_page_monitoring,
            "instagram":     self._build_page_instagram,
        }
        for key, builder in builders.items():
            frame = ctk.CTkScrollableFrame(self._content, fg_color=T["bg_base"],
                                           corner_radius=0,
                                           scrollbar_button_color=T["bg_elevated"],
                                           scrollbar_button_hover_color=T["bg_hover"])
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            builder(frame)
            self._pages[key] = frame

    def _navigate(self, page: str):
        for key, frame in self._pages.items():
            frame.grid_remove() if key != page else frame.grid()
        for key, btn in self._nav_btns.items():
            btn.set_active(key == page)

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Mensagens
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_messages(self, parent):
        pad = {"padx": 32, "pady": 0}

        hdr = _section_header(parent, "Mensagens",
                               "Configure o que será enviado. Cada bloco = uma mensagem.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        # Dica de sintaxe
        tip = _card(parent)
        tip.pack(fill="x", **pad)
        tip.columnconfigure(0, weight=1)
        ctk.CTkLabel(tip,
                     text="Use {nome} para personalizar  •  Use [opção1/opção2] para variar automaticamente",
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            side="left", padx=16, pady=10)
        Tooltip(tip, "Exemplo: 'Olá [João/amigo]' → cada contato recebe uma variação diferente")

        _divider(parent)

        # Área de blocos + prévia
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, **pad)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Coluna esquerda: blocos
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.blocks_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent",
                                                     scrollbar_button_color=T["bg_elevated"])
        self.blocks_scroll.grid(row=0, column=0, sticky="nsew")
        self.blocks_scroll.columnconfigure(0, weight=1)

        # Botões de ação
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        ctk.CTkButton(btn_row, text="+ Bloco", image=ic.add(16), compound="left",
                      command=lambda: self._add_block(),
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Salvar", image=ic.save(16), compound="left",
                      command=self._save_messages,
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["bg_elevated"],
                      hover_color=T["bg_hover"]).pack(side="left", padx=(0, 8))

        # Coluna direita: imagem + prévia
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        # Card imagem
        img_card = _card(right)
        img_card.pack(fill="x", pady=(0, 12))
        img_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(img_card, text="Imagem (opcional)",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(img_card, text="Enviada antes das mensagens de texto.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(0, 8))

        self.img_thumb = ctk.CTkLabel(img_card, text="Nenhuma imagem selecionada",
                                      font=F["label"], text_color=T["text_3"],
                                      height=100)
        self.img_thumb.pack(padx=16, pady=(0, 8))

        img_btns = ctk.CTkFrame(img_card, fg_color="transparent")
        img_btns.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(img_btns, text="Selecionar", image=ic.folder(16), compound="left",
                      command=self._pick_image,
                      height=34, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).pack(
            side="left", padx=(0, 8))
        self.remove_img_btn = ctk.CTkButton(img_btns, text="Remover",
                                             image=ic.trash(16), compound="left",
                                             command=self._remove_image, state="disabled",
                                             height=34, corner_radius=T["r_btn"], font=F["body"],
                                             fg_color=T["bg_elevated"],
                                             hover_color=T["bg_hover"])
        self.remove_img_btn.pack(side="left")

        # Botão prévia
        ctk.CTkButton(right, text="Ver Prévia", image=ic.export_icon(16), compound="left",
                      command=self._show_preview,
                      height=42, corner_radius=T["r_btn"], font=F["subhead"],
                      fg_color="#7C3AED", hover_color="#6D28D9").pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(right, text="Veja como ficará para o destinatário",
                     font=F["label_sm"], text_color=T["text_3"]).pack()

        # Carregar blocos iniciais
        for b in self.blocos:
            self._add_block(b)

    def _add_block(self, text: str = ""):
        idx = len(self.block_widgets) + 1
        frame = _card(self.blocks_scroll)
        frame.grid(row=idx - 1, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=f"#{idx}", font=("Consolas", 11, "bold"),
                     text_color=T["accent"], width=32).grid(
            row=0, column=0, padx=(14, 8), pady=14, sticky="nw")

        col = ctk.CTkFrame(frame, fg_color="transparent")
        col.grid(row=0, column=1, padx=(0, 8), pady=12, sticky="ew")
        col.columnconfigure(0, weight=1)

        box = ctk.CTkTextbox(col, height=80, corner_radius=T["r_btn"],
                             fg_color=T["bg_elevated"], text_color=T["text_1"],
                             font=F["body"], border_color=T["border"], border_width=1)
        box.grid(row=0, column=0, sticky="ew")
        box.insert("0.0", text if text else "Coloque seu texto aqui")

        ctk.CTkButton(col, text="Inserir {nome}",
                      command=lambda b=box: b.insert(tk.INSERT, "{nome}"),
                      height=26, corner_radius=T["r_pill"], font=F["label_sm"],
                      fg_color=T["bg_base"], hover_color=T["bg_hover"],
                      text_color=T["accent"]).grid(row=1, column=0, sticky="w", pady=(4, 0))

        def _rm(f=frame, b=box):
            self.block_widgets = [(fr, bx) for fr, bx in self.block_widgets if bx is not b]
            f.destroy()
            self._renumber_blocks()

        ctk.CTkButton(frame, text="", image=ic.close(13), command=_rm,
                      width=30, height=30, corner_radius=T["r_btn"],
                      fg_color="#3D1010",
                      hover_color=T["danger"]).grid(
            row=0, column=2, padx=(0, 12), pady=14, sticky="n")

        self.block_widgets.append((frame, box))

    def _renumber_blocks(self):
        for i, (frame, _) in enumerate(self.block_widgets):
            frame.grid(row=i, column=0, sticky="ew", pady=(0, 10))
            for child in frame.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("text").startswith("#"):
                    child.configure(text=f"#{i + 1}")

    def _save_messages(self):
        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso", "Adicione pelo menos uma mensagem.")
            return
        self.blocos = blocos
        self._messages_path().write_text(
            json.dumps(blocos, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log(f"Mensagens salvas: {len(blocos)} bloco(s).")
        messagebox.showinfo("Salvo", f"{len(blocos)} mensagem(ns) salva(s).")

    def _pick_image(self):
        path = filedialog.askopenfilename(
            title="Selecionar imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("Todos", "*.*")])
        if not path:
            return
        self.image_path = path
        try:
            pil = PILImage.open(path).convert("RGBA")
            pil.thumbnail((200, 100))
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
            self.img_thumb.configure(image=ctk_img, text="")
            self.img_thumb._image = ctk_img
        except Exception:
            self.img_thumb.configure(image=None, text=Path(path).name)
        self.remove_img_btn.configure(state="normal")

    def _remove_image(self):
        self.image_path = None
        self.img_thumb.configure(image=None, text="Nenhuma imagem selecionada")
        self.remove_img_btn.configure(state="disabled")

    def _show_preview(self):
        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso", "Adicione pelo menos uma mensagem.")
            return
        PreviewWindow(self, blocos, self.image_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Contatos
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_contacts(self, parent):
        pad = {"padx": 32}

        hdr = _section_header(parent, "Contatos",
                               "Gerencie quem vai receber as mensagens.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        # Formulário individual
        form = _card(parent)
        form.pack(fill="x", **pad, pady=(0, 12))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ctk.CTkLabel(form, text="Adicionar contato",
                     font=F["subhead"], text_color=T["text_1"]).grid(
            row=0, column=0, columnspan=5, sticky="w", padx=16, pady=(14, 10))

        ctk.CTkLabel(form, text="Nome", font=F["label"],
                     text_color=T["text_3"]).grid(row=1, column=0, padx=(16, 8), pady=(0, 14))
        ne = ctk.CTkEntry(form, textvariable=self.name_var, height=38,
                          corner_radius=T["r_btn"], font=F["body"],
                          placeholder_text="Ex: Maria Silva",
                          fg_color=T["bg_elevated"], border_color=T["border"])
        ne.grid(row=1, column=1, padx=(0, 16), pady=(0, 14), sticky="ew")
        ne.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkLabel(form, text="Telefone", font=F["label"],
                     text_color=T["text_3"]).grid(row=1, column=2, padx=(0, 8), pady=(0, 14))
        pe = ctk.CTkEntry(form, textvariable=self.phone_var, height=38,
                          corner_radius=T["r_btn"], font=F["body"],
                          placeholder_text="Ex: 11987654321",
                          fg_color=T["bg_elevated"], border_color=T["border"])
        pe.grid(row=1, column=3, padx=(0, 16), pady=(0, 14), sticky="ew")
        pe.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkButton(form, text="Adicionar", image=ic.add(16), compound="left",
                      command=self.add_contact,
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).grid(
            row=1, column=4, padx=(0, 16), pady=(0, 14))

        # Colar em massa
        mass_card = _card(parent)
        mass_card.pack(fill="x", **pad, pady=(0, 12))
        mass_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(mass_card, text="Colar em massa",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(mass_card, text="Cole uma coluna de nomes e uma de telefones direto do Excel ou Google Sheets.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(anchor="w", padx=16, pady=(0, 10))

        cols = ctk.CTkFrame(mass_card, fg_color="transparent")
        cols.pack(fill="x", padx=16, pady=(0, 12))
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        nc = ctk.CTkFrame(cols, fg_color="transparent")
        nc.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        nc.columnconfigure(0, weight=1)
        ctk.CTkLabel(nc, text="Nomes  (um por linha)",
                     font=F["label"], text_color=T["text_3"]).pack(anchor="w", pady=(0, 4))
        self.mass_names = ctk.CTkTextbox(nc, height=100, corner_radius=T["r_btn"],
                                          fg_color=T["bg_elevated"], text_color=T["text_1"],
                                          font=F["body"], border_color=T["border"],
                                          border_width=1)
        self.mass_names.pack(fill="x")

        pc = ctk.CTkFrame(cols, fg_color="transparent")
        pc.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        pc.columnconfigure(0, weight=1)
        ctk.CTkLabel(pc, text="Telefones  (um por linha)",
                     font=F["label"], text_color=T["text_3"]).pack(anchor="w", pady=(0, 4))
        self.mass_phones = ctk.CTkTextbox(pc, height=100, corner_radius=T["r_btn"],
                                           fg_color=T["bg_elevated"], text_color=T["text_1"],
                                           font=F["body"], border_color=T["border"],
                                           border_width=1)
        self.mass_phones.pack(fill="x")

        ctk.CTkButton(mass_card, text="Adicionar Todos",
                      image=ic.check(16), compound="left",
                      command=self.add_contacts_bulk,
                      height=38, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).pack(
            anchor="w", padx=16, pady=(0, 14))

        # Toolbar CSV
        csv_bar = ctk.CTkFrame(parent, fg_color="transparent")
        csv_bar.pack(fill="x", **pad, pady=(0, 10))

        def _tbtn(text, cmd, img):
            return ctk.CTkButton(csv_bar, text=text, image=img, compound="left",
                                 command=cmd, height=36, corner_radius=T["r_btn"],
                                 font=F["body"], fg_color=T["bg_surface"],
                                 hover_color=T["bg_hover"])

        _tbtn("Carregar CSV", self.load_contacts_from_csv, ic.folder(16)).pack(side="left", padx=(0, 6))
        _tbtn("Salvar CSV",   self.save_contacts_to_csv,   ic.save(16)  ).pack(side="left", padx=6)
        _tbtn("Remover",      self.remove_selected,         ic.trash(16) ).pack(side="left", padx=6)
        _tbtn("Exportar",     self.export_report,           ic.chart(16) ).pack(side="left", padx=6)

        # Tabela
        table_card = _card(parent)
        table_card.pack(fill="both", expand=True, **pad, pady=(0, 24))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(1, weight=1)

        ctk.CTkLabel(table_card, text="Lista de Contatos",
                     font=F["subhead"], text_color=T["text_1"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        tree_host = tk.Frame(table_card, bg=T["bg_elevated"], bd=0, highlightthickness=0)
        tree_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tree_host.columnconfigure(0, weight=1)
        tree_host.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_host, columns=("nome", "telefone", "status"),
                                  show="headings", style="Z.Treeview")
        self.tree.heading("nome",     text="  Nome")
        self.tree.heading("telefone", text="  Telefone")
        self.tree.heading("status",   text="Status")
        self.tree.column("nome",     width=280, anchor="w",      stretch=True)
        self.tree.column("telefone", width=200, anchor="w",      stretch=True)
        self.tree.column("status",   width=120, anchor="center", stretch=False)
        self.tree.tag_configure("enviado",  foreground=T["success"])
        self.tree.tag_configure("falha",    foreground=T["danger"])
        self.tree.tag_configure("enviando", foreground=T["warning"])
        self.tree.tag_configure("pendente", foreground=T["text_3"])

        vsb = ttk.Scrollbar(tree_host, orient="vertical", command=self.tree.yview,
                            style="Z.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Tempo & Delay
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_timing(self, parent):
        hdr = _section_header(parent, "Tempo & Delay",
                               "Configure os intervalos entre mensagens e contatos.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        def _row(parent, label, hint=""):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            ctk.CTkLabel(f, text=label, font=F["body"], text_color=T["text_1"]).pack(
                side="left", padx=(0, 8))
            if hint:
                ctk.CTkLabel(f, text=hint, font=F["label_sm"],
                             text_color=T["text_3"]).pack(side="left")
            return f

        # Card delay entre mensagens
        c1 = _card(parent)
        c1.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(c1, text="Delay entre mensagens",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(c1, text="Tempo de espera entre cada bloco enviado para o mesmo contato.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(anchor="w", padx=16, pady=(0, 12))

        mode_row = ctk.CTkFrame(c1, fg_color="transparent")
        mode_row.pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkRadioButton(mode_row, text="Fixo", variable=self.delay_mode, value="fixo",
                           command=self._on_delay_mode_change, font=F["body"]).pack(
            side="left", padx=(0, 24))
        ctk.CTkRadioButton(mode_row, text="Aleatório", variable=self.delay_mode, value="aleatorio",
                           command=self._on_delay_mode_change, font=F["body"]).pack(side="left")

        self._fixo_frame = ctk.CTkFrame(c1, fg_color="transparent")
        self._fixo_frame.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(self._fixo_frame, text="Aguardar",
                     font=F["body"], text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(self._fixo_frame, textvariable=self.delay_fixo_var,
                     width=70, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self._fixo_frame, text="segundos",
                     font=F["body"], text_color=T["text_2"]).pack(side="left")

        self._rand_frame = ctk.CTkFrame(c1, fg_color="transparent")
        self._rand_frame.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(self._rand_frame, text="Entre",
                     font=F["body"], text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(self._rand_frame, textvariable=self.delay_min_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self._rand_frame, text="e",
                     font=F["body"], text_color=T["text_2"]).pack(side="left", padx=8)
        ctk.CTkEntry(self._rand_frame, textvariable=self.delay_max_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self._rand_frame, text="segundos (aleatório)",
                     font=F["body"], text_color=T["text_2"]).pack(side="left")

        self._on_delay_mode_change()

        # Card pausa entre contatos
        c2 = _card(parent)
        c2.pack(fill="x", padx=32, pady=(0, 12))
        ctk.CTkLabel(c2, text="Pausa entre contatos",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(c2,
                     text="Tempo de descanso antes de passar para o próximo contato.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(anchor="w", padx=16, pady=(0, 10))

        pause_row = ctk.CTkFrame(c2, fg_color="transparent")
        pause_row.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(pause_row, text="De", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(pause_row, textvariable=self.pause_min_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pause_row, text="a", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=8)
        ctk.CTkEntry(pause_row, textvariable=self.pause_max_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pause_row, text="segundos", font=F["body"],
                     text_color=T["text_2"]).pack(side="left")

    def _on_delay_mode_change(self):
        if self.delay_mode.get() == "fixo":
            self._rand_frame.pack_forget()
            self._fixo_frame.pack(anchor="w", padx=16, pady=(0, 14))
        else:
            self._fixo_frame.pack_forget()
            self._rand_frame.pack(anchor="w", padx=16, pady=(0, 14))

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Anti-Bloqueio
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_antiblock(self, parent):
        hdr = _section_header(parent, "Proteção Anti-Bloqueio",
                               "Configure as camadas de proteção contra detecção pelo WhatsApp.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        def _toggle_card(parent, title, desc, var, extra_fn=None):
            c = _card(parent)
            c.pack(fill="x", padx=32, pady=(0, 12))
            c.columnconfigure(0, weight=1)
            top = ctk.CTkFrame(c, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(14, 4))
            top.columnconfigure(0, weight=1)
            ctk.CTkLabel(top, text=title, font=F["subhead"],
                         text_color=T["text_1"]).grid(row=0, column=0, sticky="w")
            ctk.CTkSwitch(top, text="", variable=var, width=46,
                          progress_color=T["accent"],
                          command=extra_fn).grid(row=0, column=1, sticky="e")
            ctk.CTkLabel(c, text=desc, font=F["body_sm"],
                         text_color=T["text_3"], wraplength=700,
                         justify="left").pack(anchor="w", padx=16, pady=(0, 12))
            return c

        # Limite diário
        c1 = _toggle_card(parent, "Limite Diário",
                          "Define quantos envios podem ser feitos por dia. O contador reinicia à meia-noite.",
                          self.daily_limit_enabled)
        lim_row = ctk.CTkFrame(c1, fg_color="transparent")
        lim_row.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(lim_row, text="Máximo de", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(lim_row, textvariable=self.daily_limit_var,
                     width=70, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(lim_row, text="envios por dia", font=F["body"],
                     text_color=T["text_2"]).pack(side="left")
        Tooltip(lim_row, "Recomendado: até 80/dia para contas com +30 dias de uso")

        # Warm-up
        c2 = _toggle_card(parent, "Modo Aquecimento (Warm-up)",
                          "Aumenta o limite automaticamente conforme o número de dias de uso.\n"
                          "Dia 1 → 10  ·  Dia 2 → 20  ·  Dia 3 → 35  ·  Dia 7 → 70  ·  Dia 14+ → 200",
                          self.warmup_enabled)
        ctk.CTkLabel(c2, textvariable=self.warmup_status_var,
                     font=F["mono_sm"], text_color=T["accent"]).pack(
            anchor="w", padx=16, pady=(0, 14))

        # Horário humano
        c3 = _toggle_card(parent, "Horário Humanizado",
                          "Só envia dentro do intervalo configurado. Fora do horário, aguarda automaticamente.",
                          self.human_hours_enabled)
        h_row = ctk.CTkFrame(c3, fg_color="transparent")
        h_row.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(h_row, text="Das", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(h_row, textvariable=self.hours_start_var,
                     width=70, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(h_row, text="às", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=8)
        ctk.CTkEntry(h_row, textvariable=self.hours_end_var,
                     width=70, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))

        # Velocidade de digitação
        spd = _card(parent)
        spd.pack(fill="x", padx=32, pady=(0, 12))
        ctk.CTkLabel(spd, text="Velocidade de Digitação",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(spd,
                     text="Define a rapidez com que as mensagens são digitadas. Aleatório sorteia por sessão.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(0, 10))
        ctk.CTkSegmentedButton(spd, values=["Lenta", "Media", "Rapida", "Aleatorio"],
                               variable=self.typing_profile_var,
                               font=F["body"],
                               selected_color=T["accent"],
                               selected_hover_color=T["accent_hover"],
                               unselected_color=T["bg_elevated"],
                               unselected_hover_color=T["bg_hover"]).pack(
            anchor="w", padx=16, pady=(0, 14))

        # Sessões
        c4 = _toggle_card(parent, "Divisão em Sessões",
                          "Divide o envio em blocos menores com pausa entre eles. Reduz padrão de envio em massa.",
                          self.session_split_enabled)
        s_row = ctk.CTkFrame(c4, fg_color="transparent")
        s_row.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(s_row, text="", font=F["body"],
                     text_color=T["text_2"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(s_row, textvariable=self.session_size_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(s_row, text="por sessão, pausa de",
                     font=F["body"], text_color=T["text_2"]).pack(side="left", padx=8)
        ctk.CTkEntry(s_row, textvariable=self.session_pause_var,
                     width=65, height=34, corner_radius=T["r_btn"],
                     fg_color=T["bg_elevated"], font=F["mono"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(s_row, text="minutos", font=F["body"],
                     text_color=T["text_2"]).pack(side="left")

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Monitoramento
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_monitoring(self, parent):
        hdr = _section_header(parent, "Monitoramento",
                               "Acompanhe o envio em tempo real.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Coluna esquerda: status ao vivo + progresso
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        # Card "Enviando agora"
        now_card = _card(left)
        now_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(now_card, text="Enviando agora",
                     font=F["label"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(now_card, textvariable=self.live_contact_var,
                     font=("Segoe UI", 20, "bold"), text_color=T["accent"]).pack(
            anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(now_card, textvariable=self.live_msg_var,
                     font=F["mono_sm"], text_color=T["text_2"],
                     wraplength=380, justify="left").pack(
            anchor="w", padx=16, pady=(0, 8))
        ctk.CTkFrame(now_card, fg_color=T["border"], height=1).pack(
            fill="x", padx=16, pady=4)
        ctk.CTkLabel(now_card, textvariable=self.live_next_var,
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(4, 14))

        # Progresso
        prog_card = _card(left)
        prog_card.pack(fill="x", pady=(0, 12))

        self.summary_var = tk.StringVar(value="0 / 0 concluídos")
        ctk.CTkLabel(prog_card, textvariable=self.summary_var,
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 8))
        self.progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5,
                                                fg_color=T["border"],
                                                progress_color=T["accent"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 16))

        # Coluna direita: log
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        log_card = _card(right)
        log_card.grid(row=0, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        log_hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(log_hdr, text="Log de Atividade",
                     font=F["subhead"], text_color=T["text_1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(log_hdr, text="Limpar", image=ic.close(13), compound="left",
                      command=self.clear_log,
                      width=80, height=28, corner_radius=T["r_btn"], font=F["label_sm"],
                      fg_color=T["bg_elevated"],
                      hover_color=T["bg_hover"]).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_card, font=F["mono_sm"], corner_radius=T["r_btn"],
                                       fg_color=T["bg_elevated"], text_color=T["text_2"],
                                       state="disabled", wrap="word",
                                       border_color=T["border"], border_width=1)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

    # ──────────────────────────────────────────────────────────────────────────
    # Onboarding
    # ──────────────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────────────
    # Página: Instagram DM
    # ──────────────────────────────────────────────────────────────────────────

    def _build_page_instagram(self, parent):
        hdr = _section_header(parent, "Instagram DM",
                               "Envie mensagens diretas para clientes no Instagram via Chrome.")
        hdr.pack(fill="x", padx=32, pady=(28, 20))

        # ── Instrução ─────────────────────────────────────────────────────────
        info_card = _card(parent)
        info_card.pack(fill="x", padx=32, pady=(0, 12))

        aviso = ctk.CTkFrame(info_card, fg_color=T["accent_dim"], corner_radius=8)
        aviso.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(aviso,
                     text="O ZapFlow usa o app do Instagram instalado no Windows.\n"
                          "Certifique-se de que o app está instalado e você está logado.\n"
                          "O app será aberto automaticamente ao iniciar.",
                     font=F["body_sm"], text_color=T["text_1"],
                     justify="left").pack(anchor="w", padx=12, pady=10)

        # ── Usuários ──────────────────────────────────────────────────────────
        users_card = _card(parent)
        users_card.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(users_card, text="Usuários do Instagram",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(users_card,
                     text="Cole os @usernames, um por linha. O @ é opcional.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(0, 8))

        self.ig_users_box = ctk.CTkTextbox(users_card, height=120, corner_radius=T["r_btn"],
                                            fg_color=T["bg_elevated"], text_color=T["text_1"],
                                            font=F["mono"], border_color=T["border"],
                                            border_width=1)
        self.ig_users_box.pack(fill="x", padx=16, pady=(0, 14))

        # ── Mensagens ─────────────────────────────────────────────────────────
        msg_card = _card(parent)
        msg_card.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(msg_card, text="Mensagens",
                     font=F["subhead"], text_color=T["text_1"]).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(msg_card,
                     text="Use {nome} para personalizar. Cada bloco = uma mensagem separada.",
                     font=F["body_sm"], text_color=T["text_3"]).pack(
            anchor="w", padx=16, pady=(0, 8))

        self.ig_msg_scroll = ctk.CTkScrollableFrame(msg_card, fg_color="transparent",
                                                     height=200)
        self.ig_msg_scroll.pack(fill="x", padx=16, pady=(0, 8))
        self.ig_msg_scroll.columnconfigure(0, weight=1)
        self.ig_msg_widgets: list[ctk.CTkTextbox] = []

        msg_btns = ctk.CTkFrame(msg_card, fg_color="transparent")
        msg_btns.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkButton(msg_btns, text="+ Mensagem", image=ic.add(16), compound="left",
                      command=self._ig_add_msg,
                      height=34, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["accent"], hover_color=T["accent_hover"]).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(msg_btns, text="Limpar tudo", image=ic.trash(16), compound="left",
                      command=self._ig_clear_msgs,
                      height=34, corner_radius=T["r_btn"], font=F["body"],
                      fg_color=T["bg_elevated"], hover_color=T["bg_hover"]).pack(side="left")

        # Bloco inicial
        self._ig_add_msg("Olá {nome}, tudo bem?")

        # ── Controles ─────────────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkButton(ctrl, text="INICIAR INSTAGRAM",
                      image=ic.play(18), compound="left",
                      command=self._ig_start,
                      height=48, corner_radius=T["r_btn"], font=F["heading"],
                      fg_color="#E1306C", hover_color="#C1215C").pack(
            side="left", padx=(0, 12))

        ctk.CTkButton(ctrl, text="Parar",
                      image=ic.stop(16), compound="left",
                      command=self._ig_stop,
                      height=48, corner_radius=T["r_btn"], font=F["subhead"],
                      fg_color=T["danger"], hover_color="#D93535").pack(side="left")

        ctk.CTkLabel(ctrl, textvariable=self.ig_status_var,
                     font=F["body"], text_color=T["accent"]).pack(
            side="left", padx=20)

        # ── Log ───────────────────────────────────────────────────────────────
        log_card = _card(parent)
        log_card.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        ctk.CTkLabel(log_card, text="Log do Instagram",
                     font=F["subhead"], text_color=T["text_1"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 0))

        self.ig_log_box = ctk.CTkTextbox(log_card, font=F["mono_sm"], corner_radius=T["r_btn"],
                                          fg_color=T["bg_elevated"], text_color=T["text_2"],
                                          state="disabled", wrap="word",
                                          border_color=T["border"], border_width=1)
        self.ig_log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

    def _ig_add_msg(self, text: str = ""):
        idx = len(self.ig_msg_widgets) + 1
        frame = _card(self.ig_msg_scroll)
        frame.grid(row=idx - 1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 0))
        header.columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=f"Mensagem {idx}", font=F["label"],
                     text_color=T["accent"]).pack(side="left")

        def _rm(f=frame, widgets=self.ig_msg_widgets):
            if box in widgets:
                widgets.remove(box)
            f.destroy()

        ctk.CTkButton(header, text="", image=ic.close(12), command=_rm,
                      width=26, height=26, corner_radius=T["r_btn"],
                      fg_color=T["danger"] + "55" if False else "#3D1010",
                      hover_color=T["danger"]).pack(side="right")

        box = ctk.CTkTextbox(frame, height=70, corner_radius=T["r_btn"],
                             fg_color=T["bg_elevated"], text_color=T["text_1"],
                             font=F["body"], border_color=T["border"], border_width=1)
        box.pack(fill="x", padx=12, pady=(4, 10))
        box.insert("0.0", text if text else "Coloque sua mensagem aqui")
        self.ig_msg_widgets.append(box)

    def _ig_clear_msgs(self):
        for widget in self.ig_msg_scroll.winfo_children():
            widget.destroy()
        self.ig_msg_widgets.clear()
        self._ig_add_msg()

    def _ig_log(self, msg: str):
        self.ig_log_box.configure(state="normal")
        self.ig_log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.ig_log_box.see(tk.END)
        self.ig_log_box.configure(state="disabled")

    def _ig_log_safe(self, msg: str):
        self.after(0, lambda: self._ig_log(msg))

    def _ig_stop(self):
        self.ig_stop = True
        self.ig_status_var.set("Parando...")
        self._ig_log_safe("Parada solicitada.")

    def _ig_start(self):
        if self.ig_running:
            return

        # Coleta usuários
        raw = self.ig_users_box.get("0.0", "end").strip().splitlines()
        usernames = [u.strip().lstrip("@") for u in raw if u.strip()]
        if not usernames:
            messagebox.showwarning("Aviso", "Cole pelo menos um @username.")
            return

        # Coleta mensagens
        messages = [box.get("0.0", "end").strip()
                    for box in self.ig_msg_widgets
                    if box.get("0.0", "end").strip()]
        if not messages:
            messagebox.showwarning("Aviso", "Adicione pelo menos uma mensagem.")
            return

        self.ig_running = True
        self.ig_stop    = False
        self.ig_status_var.set("Iniciando...")

        # Minimiza o ZapFlow para que não roube o foco durante a digitação
        self.iconify()

        threading.Thread(
            target=self._ig_send_all,
            args=(usernames, messages),
            daemon=True
        ).start()

    def _ig_send_all(self, usernames: list[str], messages: list[str]):
        total = len(usernames)

        self._ig_log_safe("Abrindo app do Instagram...")
        try:
            abrir_app_instagram()
            self._ig_log_safe("App aberto. Iniciando envios...")
        except Exception as e:
            self._ig_log_safe(f"Erro ao abrir Instagram: {e}")
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            self.ig_running = False
            self.after(0, lambda: self.ig_status_var.set("Erro"))
            return

        for idx, username in enumerate(usernames):
            if self.ig_stop:
                break

            self._ig_log_safe(f"[{idx + 1}/{total}] Enviando para @{username}...")
            self.after(0, lambda u=username: self.ig_status_var.set(f"Enviando → @{u}"))

            def _cb(bi, bt, texto):
                pv = texto[:50] + ("..." if len(texto) > 50 else "")
                self._ig_log_safe(f"  Msg {bi}/{bt}: {pv}")

            try:
                enviar_instagram(username, messages, progress_callback=_cb)
                self._ig_log_safe(f"[{idx + 1}/{total}] Concluido: @{username}")

                if idx < total - 1 and not self.ig_stop:
                    pausa = random.uniform(8, 20)
                    self._ig_log_safe(f"Aguardando {pausa:.0f}s antes do proximo...")
                    time.sleep(pausa)

            except InstagramUserNotFound:
                self._ig_log_safe(f"[{idx + 1}/{total}] Perfil nao encontrado: @{username}")
            except InstagramDMError as e:
                self._ig_log_safe(f"[{idx + 1}/{total}] Erro DM @{username}: {e}")
            except Exception as e:
                self._ig_log_safe(f"[{idx + 1}/{total}] Erro @{username}: {e}")

        self.ig_running = False
        status = "Concluido" if not self.ig_stop else "Parado"
        self.after(0, lambda: self.ig_status_var.set(status))
        self._ig_log_safe(f"Processo finalizado — {status}.")
        # Restaura a janela do ZapFlow
        self.after(0, self.deiconify)

    # ──────────────────────────────────────────────────────────────────────────
    # Onboarding
    # ──────────────────────────────────────────────────────────────────────────

    def _onboarding_done_path(self) -> Path:
        return _user_data_dir() / "onboarding_done.json"

    def _check_onboarding(self):
        if not self._onboarding_done_path().exists():
            self.after(400, self._show_onboarding)

    def _show_onboarding(self):
        def done():
            self._onboarding_done_path().write_text("{}", encoding="utf-8")
        OnboardingOverlay(self, done)

    # ──────────────────────────────────────────────────────────────────────────
    # Thread-safe helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _log_safe(self, msg: str):
        self.after(0, lambda: self.log(msg))

    def _set_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))

    # ──────────────────────────────────────────────────────────────────────────
    # Delay helpers
    # ──────────────────────────────────────────────────────────────────────────

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
                avg = float(self.delay_fixo_var.get())
            else:
                avg = (float(self.delay_min_var.get()) + float(self.delay_max_var.get())) / 2
            avg_pause = (float(self.pause_min_var.get()) + float(self.pause_max_var.get())) / 2
            return int(n_contacts * (8 + n_blocks * avg + avg_pause))
        except ValueError:
            return 0

    @staticmethod
    def _format_time(seconds: int) -> str:
        if seconds <= 0: return "0seg"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:  return f"{h}h {m}min {s}s"
        if m > 0:  return f"{m}min {s}s"
        return f"{s}seg"

    def _tick_countdown(self):
        if not self.running:
            self.countdown_var.set("")
            return
        elapsed   = int(time.time() - self._start_time)
        remaining = max(0, self._estimated_total - elapsed)
        self.countdown_var.set(f"Restante: {self._format_time(remaining)}")
        self._countdown_id = self.after(1000, self._tick_countdown)

    # ──────────────────────────────────────────────────────────────────────────
    # Anti-ban helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _is_human_hour(self) -> bool:
        if not self.human_hours_enabled.get():
            return True
        from datetime import datetime as _dt
        now = _dt.now()
        try:
            sh, sm = map(int, self.hours_start_var.get().split(":"))
            eh, em = map(int, self.hours_end_var.get().split(":"))
            start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
            end   = now.replace(hour=eh, minute=em, second=0, microsecond=0)
            return start <= now <= end
        except Exception:
            return True

    def _effective_daily_limit(self) -> int:
        if self.warmup_enabled.get():
            return self._daily_stats.warmup_limit()
        if self.daily_limit_enabled.get():
            try:
                return int(self.daily_limit_var.get())
            except ValueError:
                pass
        return 0

    # ──────────────────────────────────────────────────────────────────────────
    # Contatos
    # ──────────────────────────────────────────────────────────────────────────

    def add_contact(self):
        nome     = self.name_var.get().strip()
        telefone = self.phone_var.get().strip()
        if not nome or not telefone:
            messagebox.showwarning("Aviso", "Preencha nome e telefone.")
            return
        try:
            telefone = validate_phone(telefone)
        except Exception as exc:
            messagebox.showerror("Erro", f"Telefone inválido: {exc}")
            return
        self.contacts.append({"nome": nome, "telefone": telefone, "status": "Pendente"})
        self.refresh_table()
        self.name_var.set("")
        self.phone_var.set("")
        self.log(f"Contato adicionado: {nome} ({telefone})")

    def add_contacts_bulk(self, silent: bool = False):
        names  = [n.strip() for n in self.mass_names.get("0.0", "end").splitlines() if n.strip()]
        phones = [p.strip() for p in self.mass_phones.get("0.0", "end").splitlines() if p.strip()]
        if not names or not phones:
            if not silent:
                messagebox.showwarning("Aviso", "Cole os nomes e os telefones antes de adicionar.")
            return
        if len(names) != len(phones):
            messagebox.showwarning("Quantidades diferentes",
                                   f"{len(names)} nome(s) e {len(phones)} telefone(s).")
            return
        added, errors = 0, []
        for nome, fone in zip(names, phones):
            try:
                self.contacts.append({"nome": nome, "telefone": validate_phone(fone),
                                      "status": "Pendente"})
                added += 1
            except Exception as exc:
                errors.append(f"{nome}: {exc}")
        self.refresh_table()
        self.mass_names.delete("0.0", "end")
        self.mass_phones.delete("0.0", "end")
        if errors:
            messagebox.showwarning("Concluído com avisos",
                                   f"{added} adicionado(s).\n{len(errors)} ignorado(s):\n" +
                                   "\n".join(errors))
        elif not silent:
            messagebox.showinfo("Sucesso", f"{added} contato(s) adicionado(s).")
        self.log(f"{added} contatos adicionados em massa.")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um contato.")
            return
        values = self.tree.item(sel[0])["values"]
        nome   = values[0] if values else ""
        if messagebox.askyesno("Confirmar", f"Remover {nome}?"):
            for idx, c in enumerate(self.contacts):
                if c["nome"] == values[0] and c["telefone"] == values[1]:
                    del self.contacts[idx]
                    break
            self.refresh_table()

    def load_contacts_from_csv(self):
        path = filedialog.askopenfilename(
            title="Selecionar CSV",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        try:
            contatos = read_contacts(path)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self.contacts = [{"nome": c["nome"], "telefone": c["telefone"], "status": "Pendente"}
                         for c in contatos]
        self.refresh_table()
        self.log(f"{len(self.contacts)} contatos carregados de {Path(path).name}.")

    def _auto_load_csv(self):
        default = _user_data_dir() / config.CSV_FILE
        if not default.exists():
            return
        try:
            contatos = read_contacts(str(default))
            self.contacts = [{"nome": c["nome"], "telefone": c["telefone"], "status": "Pendente"}
                             for c in contatos]
            self.refresh_table()
        except Exception:
            pass

    def save_contacts_to_csv(self):
        path = filedialog.asksaveasfilename(
            title="Salvar CSV", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="contatos.csv")
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("nome,telefone\n")
            for c in self.contacts:
                f.write(f"{c['nome']},{c['telefone']}\n")
        messagebox.showinfo("Salvo", f"Lista salva em:\n{path}")

    def export_report(self):
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        rpath = Path(f"relatorio_{ts}.txt")
        total   = len(self.contacts)
        sent    = sum(1 for c in self.contacts if c.get("status") == "Enviado")
        failed  = sum(1 for c in self.contacts if c.get("status") == "Falha")
        lines   = [
            "=" * 65,
            f"  RELATORIO DE ENVIO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"  Total: {total}   Enviados: {sent}   Falhas: {failed}",
            "=" * 65,
            f"  {'Nome':<30} {'Telefone':<20} Status", "-" * 65,
        ]
        for c in self.contacts:
            lines.append(f"  {c['nome']:<30} {c['telefone']:<20} {c.get('status','')}")
        lines.append("=" * 65)
        rpath.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"Relatório exportado: {rpath}")
        messagebox.showinfo("Relatório", f"Arquivo criado:\n{rpath}")

    # ──────────────────────────────────────────────────────────────────────────
    # Tabela
    # ──────────────────────────────────────────────────────────────────────────

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.contacts:
            st = item.get("status", "Pendente")
            self.tree.insert("", "end", values=(item["nome"], item["telefone"], st),
                             tags=(st.lower(),))
        total             = len(self.contacts)
        self.sent_count   = sum(1 for c in self.contacts if c.get("status") == "Enviado")
        self.failed_count = sum(1 for c in self.contacts if c.get("status") == "Falha")
        pending           = total - self.sent_count - self.failed_count

        self.pill_total  .set("Total",    str(total))
        self.pill_sent   .set("Enviados",  str(self.sent_count))
        self.pill_failed .set("Falhas",    str(self.failed_count))
        self.pill_pending.set("Pendentes", str(pending))

        ratio = (self.sent_count + self.failed_count) / total if total else 0
        self.progress_bar.set(ratio)
        self.summary_var.set(f"{self.sent_count + self.failed_count} / {total} concluídos")
        self.last_report = (
            f"Total={total} | Enviados={self.sent_count} | "
            f"Falhas={self.failed_count} | Pendentes={pending}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Log
    # ──────────────────────────────────────────────────────────────────────────

    def log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", tk.END)
        self.log_box.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    # Controle de envio
    # ──────────────────────────────────────────────────────────────────────────

    def start_send_loop(self):
        if self.running:
            return

        names  = [n.strip() for n in self.mass_names.get("0.0", "end").splitlines() if n.strip()]
        phones = [p.strip() for p in self.mass_phones.get("0.0", "end").splitlines() if p.strip()]
        if names or phones:
            self.add_contacts_bulk(silent=True)

        if not self.contacts:
            messagebox.showwarning("Aviso", "Adicione contatos antes de iniciar.")
            return

        blocos = [box.get("0.0", "end").strip()
                  for _, box in self.block_widgets
                  if box.get("0.0", "end").strip()]
        if not blocos:
            messagebox.showwarning("Aviso", "Configure mensagens na aba Mensagens.")
            return

        self.blocos           = blocos
        self.running          = True
        self.stop_requested   = False
        self.paused           = False
        self._start_time      = time.time()
        self._estimated_total = self._estimate_total_seconds(len(self.contacts), len(blocos))

        self.pause_btn.configure(text="Pausar", image=ic.pause(16))
        self.status_var.set("Enviando...")
        self.countdown_var.set(f"Estimativa: {self._format_time(self._estimated_total)}")
        self.log(f"Iniciando: {len(self.contacts)} contatos, {len(blocos)} mensagem(ns). "
                 f"Estimativa: {self._format_time(self._estimated_total)}")
        self._tick_countdown()
        self._navigate("monitoramento")
        threading.Thread(target=self._send_all, daemon=True).start()

    def pause_send_loop(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="Retomar", image=ic.play(16))
            self._set_status("Pausado")
            self._log_safe("Envio pausado.")
        else:
            self.pause_btn.configure(text="Pausar", image=ic.pause(16))
            self._set_status("Enviando...")
            self._log_safe("Envio retomado.")

    def stop_send_loop(self):
        self.stop_requested = True
        self._set_status("Parando...")
        self._log_safe("Parada solicitada.")

    def _send_all(self):
        blocos     = list(self.blocos)
        image_path = self.image_path
        total      = len(self.contacts)
        profile    = self.typing_profile_var.get().lower()

        if self.delay_mode.get() == "fixo":
            d_min = d_max = float(self.delay_fixo_var.get())
        else:
            d_min = float(self.delay_min_var.get())
            d_max = float(self.delay_max_var.get())

        try:
            session_size  = int(self.session_size_var.get())  if self.session_split_enabled.get() else 0
            session_pause = int(self.session_pause_var.get()) if self.session_split_enabled.get() else 0
        except ValueError:
            session_size = session_pause = 0

        self._consecutive_errors = 0
        sent_this_session        = 0

        for index, item in enumerate(self.contacts):
            if self.stop_requested:
                break
            while self.paused and not self.stop_requested:
                time.sleep(0.5)
            if self.stop_requested:
                break

            # Horário humano
            if not self._is_human_hour():
                self._log_safe("Fora do horário. Aguardando...")
                self._set_status("Fora do horário")
                while not self._is_human_hour() and not self.stop_requested:
                    time.sleep(60)
                if self.stop_requested:
                    break

            # Limite diário
            limit = self._effective_daily_limit()
            if limit > 0 and not self._daily_stats.can_send(limit):
                self._log_safe(f"Limite diário de {limit} atingido.")
                break

            # Pausa de sessão
            if session_size > 0 and sent_this_session > 0 and sent_this_session % session_size == 0:
                self._log_safe(f"Sessão de {session_size} concluída. Pausa de {session_pause} min...")
                self._set_status(f"Pausa entre sessões ({session_pause} min)")
                time.sleep(session_pause * 60)

            # Erros consecutivos
            if self._consecutive_errors >= 3:
                self._log_safe("3 erros consecutivos. Pausa de segurança de 5 min...")
                time.sleep(300)
                self._consecutive_errors = 0

            nome     = item["nome"]
            telefone = item["telefone"]

            # Próximo na fila
            if index + 1 < total:
                prox = self.contacts[index + 1]["nome"]
                eta  = int(len(blocos) * (d_min + d_max) / 2 +
                           (float(self.pause_min_var.get()) + float(self.pause_max_var.get())) / 2 + 8)
                self.after(0, lambda n=prox, s=eta: self.live_next_var.set(
                    f"Próximo: {n}  (~{self._format_time(s)})"))
            else:
                self.after(0, lambda: self.live_next_var.set("Último contato"))

            self.after(0, lambda n=nome: self.live_contact_var.set(n))
            self.after(0, lambda: self.live_msg_var.set("Abrindo conversa..."))
            self._update_item_status(index, "Enviando")
            self._log_safe(f"[{index + 1}/{total}] → {nome}")

            blocos_spin = [parse_spin(b) for b in blocos]

            def _cb(bi, bt, texto):
                pv = texto[:55] + ("..." if len(texto) > 55 else "")
                self.after(0, lambda: self.live_msg_var.set(f"Msg {bi}/{bt}:\n\"{pv}\""))
                self._log_safe(f"  Msg {bi}/{bt}: {pv}")

            try:
                enviar_para(nome, telefone, blocos_spin, image_path,
                            delay_min=d_min, delay_max=d_max,
                            progress_callback=_cb,
                            typing_profile=profile)
                self._update_item_status(index, "Enviado")
                self._log_safe(f"[{index + 1}/{total}] ✓ {nome}")
                self._daily_stats.register_send()
                self.after(0, lambda: self.warmup_status_var.set(
                    self._daily_stats.status_line()))
                self._consecutive_errors = 0
                sent_this_session += 1

            except InvalidWhatsAppNumberError:
                self._update_item_status(index, "Falha")
                self._log_safe(f"[{index + 1}/{total}] ✗ Sem WhatsApp: {nome}")
                self._consecutive_errors += 1

            except Exception as exc:
                self._update_item_status(index, "Falha")
                self._log_safe(f"[{index + 1}/{total}] ✗ Erro: {nome} — {exc}")
                self._consecutive_errors += 1

            if index < total - 1 and not self.stop_requested:
                pausa = self._get_pause_delay()
                self._log_safe(f"Aguardando {pausa:.0f}s...")
                self.after(0, lambda: self.live_contact_var.set("Aguardando..."))
                self.after(0, lambda s=int(pausa): self.live_msg_var.set(
                    f"Próximo em {self._format_time(s)}"))
                time.sleep(pausa)

        self.running = False
        self.after(0, lambda: self.live_contact_var.set("—"))
        self.after(0, lambda: self.live_msg_var.set("—"))
        self.after(0, lambda: self.live_next_var.set("—"))
        self.after(0, lambda: self.countdown_var.set(""))
        self._set_status("Concluído" if not self.stop_requested else "Parado")
        self._log_safe("Processo finalizado.")
        self.after(0, lambda: FinalDashboard(self, list(self.contacts), self.export_report))

    def _update_item_status(self, index: int, status: str):
        if index < len(self.contacts):
            self.contacts[index]["status"] = status
            self.after(0, self.refresh_table)


if __name__ == "__main__":
    app = WhatsAppPanel()
    app.mainloop()
