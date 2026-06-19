import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

import config
from whatsapp_sender import enviar_para, read_contacts, validate_phone

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C = {
    "bg":      "#0f172a",
    "surface": "#1e293b",
    "card":    "#1e293b",
    "accent":  "#3b82f6",
    "success": "#10b981",
    "danger":  "#ef4444",
    "warning": "#f59e0b",
    "text":    "#f1f5f9",
    "subtext": "#94a3b8",
    "border":  "#334155",
}


def _style_treeview():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Z.Treeview",
        background=C["card"],
        foreground=C["text"],
        fieldbackground=C["card"],
        borderwidth=0,
        rowheight=34,
        font=("Segoe UI", 10),
    )
    style.configure(
        "Z.Treeview.Heading",
        background="#0f172a",
        foreground=C["subtext"],
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Z.Treeview",
        background=[("selected", C["accent"])],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Z.Vertical.TScrollbar",
        background=C["surface"],
        troughcolor=C["bg"],
        borderwidth=0,
        arrowcolor=C["subtext"],
        relief="flat",
    )


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, color: str, **kw):
        super().__init__(master, corner_radius=14, fg_color=C["surface"], **kw)
        self.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text=title,
            font=("Segoe UI", 11), text_color=C["subtext"]
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 0))

        self._val = ctk.CTkLabel(
            self, text="0",
            font=("Segoe UI", 30, "bold"), text_color=color
        )
        self._val.grid(row=1, column=0, sticky="w", padx=18, pady=(4, 16))

    def set(self, value: str):
        self._val.configure(text=value)


class WhatsAppPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ZapFlow")
        self.geometry("1300x820")
        self.minsize(1100, 700)
        self.configure(fg_color=C["bg"])
        self._set_icon()

        self.contacts: list[dict] = []
        self.running = False
        self.stop_requested = False
        self.paused = False
        self.sent_count = 0
        self.failed_count = 0
        self.last_report = "Aguardando início..."

        _style_treeview()
        self._build_ui()
        self.load_contacts_from_csv()

    def _set_icon(self):
        icon_path = Path(__file__).parent / "img" / "zapflow.png"
        if icon_path.exists():
            img = tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True, img)
            self._icon_ref = img  # evita garbage collection

    # ──────────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        self._build_header(root)
        self._build_cards(root)
        self._build_toolbar(root)
        self._build_content(root)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=14, height=68)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(1, weight=1)
        header.grid_propagate(False)

        ctk.CTkLabel(
            header, text="⚡ ZapFlow",
            font=("Segoe UI", 22, "bold"), text_color=C["accent"]
        ).grid(row=0, column=0, padx=22, sticky="w")

        ctk.CTkLabel(
            header, text="Automação de Envio via WhatsApp",
            font=("Segoe UI", 12), text_color=C["subtext"]
        ).grid(row=0, column=1, padx=8, sticky="w")

        self.status_var = tk.StringVar(value="● Pronto para iniciar")
        ctk.CTkLabel(
            header, textvariable=self.status_var,
            font=("Segoe UI", 11, "bold"), text_color=C["success"]
        ).grid(row=0, column=2, padx=22, sticky="e")

    def _build_cards(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        for i in range(4):
            row.columnconfigure(i, weight=1)

        self.card_total   = StatCard(row, "Total de Contatos", C["accent"])
        self.card_sent    = StatCard(row, "Enviados",           C["success"])
        self.card_failed  = StatCard(row, "Falhas",             C["danger"])
        self.card_pending = StatCard(row, "Pendentes",          C["warning"])

        self.card_total  .grid(row=0, column=0, padx=(0, 8),  sticky="ew")
        self.card_sent   .grid(row=0, column=1, padx=8,       sticky="ew")
        self.card_failed .grid(row=0, column=2, padx=8,       sticky="ew")
        self.card_pending.grid(row=0, column=3, padx=(8, 0),  sticky="ew")

    def _build_toolbar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=14)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(3, weight=1)

        # Linha 1: formulário
        ctk.CTkLabel(bar, text="Nome", text_color=C["subtext"], font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(18, 6), pady=(16, 0), sticky="w"
        )
        self.name_var = tk.StringVar()
        ne = ctk.CTkEntry(bar, textvariable=self.name_var, placeholder_text="Ex: João Silva", height=40, corner_radius=8)
        ne.grid(row=0, column=1, padx=(0, 18), pady=(16, 0), sticky="ew")
        ne.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkLabel(bar, text="Telefone", text_color=C["subtext"], font=("Segoe UI", 11)).grid(
            row=0, column=2, padx=(0, 6), pady=(16, 0), sticky="w"
        )
        self.phone_var = tk.StringVar()
        pe = ctk.CTkEntry(bar, textvariable=self.phone_var, placeholder_text="Ex: 11987654321", height=40, corner_radius=8)
        pe.grid(row=0, column=3, padx=(0, 18), pady=(16, 0), sticky="ew")
        pe.bind("<Return>", lambda _: self.add_contact())

        ctk.CTkButton(
            bar, text="+ Adicionar", command=self.add_contact,
            width=120, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color="#2563eb",
            font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=4, padx=(0, 18), pady=(16, 0))

        # Linha 2: ações
        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=1, column=0, columnspan=5, sticky="ew", padx=18, pady=(10, 16))

        def _btn(text, cmd, fg, hover, w=None):
            return ctk.CTkButton(
                actions, text=text, command=cmd,
                height=36, corner_radius=8,
                fg_color=fg, hover_color=hover,
                font=("Segoe UI", 11),
                **({"width": w} if w else {})
            )

        _btn("📂 Carregar CSV", self.load_contacts_from_csv, C["border"], "#475569").pack(side="left", padx=(0, 6))
        _btn("💾 Salvar CSV",   self.save_contacts_to_csv,   C["border"], "#475569").pack(side="left", padx=6)
        _btn("🗑 Remover",      self.remove_selected,         C["border"], "#475569").pack(side="left", padx=6)
        _btn("📊 Exportar",     self.export_report,           C["border"], "#475569").pack(side="left", padx=6)

        ctk.CTkLabel(actions, text="│", text_color=C["border"], font=("Segoe UI", 20)).pack(side="left", padx=12)

        _btn("▶  Iniciar", self.start_send_loop, C["success"], "#059669", 120).pack(side="left", padx=6)
        self.pause_btn = _btn("⏸  Pausar", self.pause_send_loop, C["warning"], "#d97706", 120)
        self.pause_btn.pack(side="left", padx=6)
        _btn("⏹  Parar", self.stop_send_loop, C["danger"], "#dc2626", 120).pack(side="left", padx=6)

    def _build_content(self, parent):
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=3, column=0, sticky="nsew")
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Tabela
        table_card = ctk.CTkFrame(content, fg_color=C["surface"], corner_radius=14)
        table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_card, text="Lista de Contatos",
            font=("Segoe UI", 13, "bold"), text_color=C["text"]
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        tree_host = tk.Frame(table_card, bg=C["surface"], bd=0, highlightthickness=0)
        tree_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tree_host.columnconfigure(0, weight=1)
        tree_host.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_host,
            columns=("nome", "telefone", "status"),
            show="headings",
            style="Z.Treeview",
        )
        self.tree.heading("nome",     text="  Nome")
        self.tree.heading("telefone", text="  Telefone")
        self.tree.heading("status",   text="Status")
        self.tree.column("nome",     width=260, anchor="w",      stretch=True)
        self.tree.column("telefone", width=200, anchor="w",      stretch=True)
        self.tree.column("status",   width=120, anchor="center", stretch=False)

        self.tree.tag_configure("enviado",  foreground=C["success"])
        self.tree.tag_configure("falha",    foreground=C["danger"])
        self.tree.tag_configure("enviando", foreground=C["warning"])
        self.tree.tag_configure("pendente", foreground=C["subtext"])

        vsb = ttk.Scrollbar(tree_host, orient="vertical", command=self.tree.yview, style="Z.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Painel direito
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Card de progresso
        prog = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        prog.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        prog.columnconfigure(0, weight=1)

        ctk.CTkLabel(prog, text="Progresso", font=("Segoe UI", 13, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4)
        )
        self.summary_var = tk.StringVar(value="0 / 0 concluídos")
        ctk.CTkLabel(prog, textvariable=self.summary_var, font=("Segoe UI", 11), text_color=C["subtext"]).grid(
            row=1, column=0, sticky="w", padx=16
        )
        self.progress_bar = ctk.CTkProgressBar(
            prog, height=14, corner_radius=7,
            fg_color=C["border"], progress_color=C["accent"]
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 16))

        # Card de log
        log_card = ctk.CTkFrame(right, fg_color=C["surface"], corner_radius=14)
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        log_hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(log_hdr, text="Log de Atividade", font=("Segoe UI", 13, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            log_hdr, text="Limpar", command=self.clear_log,
            width=70, height=28, corner_radius=6,
            fg_color=C["border"], hover_color="#475569",
            font=("Segoe UI", 10)
        ).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            log_card,
            font=("Consolas", 10), corner_radius=8,
            fg_color=C["bg"], text_color=C["text"],
            state="disabled", wrap="word",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

    # ──────────────────────────────────────────────────────────────────────────
    # Thread-safe helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _log_safe(self, message: str):
        self.after(0, lambda: self.log(message))

    def _set_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))

    # ──────────────────────────────────────────────────────────────────────────
    # Ações sobre contatos
    # ──────────────────────────────────────────────────────────────────────────

    def add_contact(self):
        nome     = self.name_var.get().strip()
        telefone = self.phone_var.get().strip()
        if not nome or not telefone:
            messagebox.showwarning("Aviso", "Preencha nome e telefone antes de adicionar.")
            return
        try:
            telefone_normalizado = validate_phone(telefone)
        except Exception as exc:
            messagebox.showerror("Erro", f"Telefone inválido: {exc}")
            return

        self.contacts.append({"nome": nome, "telefone": telefone_normalizado, "status": "Pendente"})
        self.refresh_table()
        self.name_var.set("")
        self.phone_var.set("")
        self.log(f"Contato adicionado: {nome} ({telefone_normalizado})")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um contato para remover.")
            return
        values = self.tree.item(sel[0])["values"]
        nome   = values[0] if len(values) > 0 else ""
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
            messagebox.showwarning("Arquivo não encontrado", f"Não foi encontrado: {config.CSV_FILE}")
            self.contacts = []
            self.refresh_table()
            return

        self.contacts = [
            {"nome": c["nome"], "telefone": c["telefone"], "status": "Pendente"}
            for c in contatos
        ]
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
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path(f"relatorio_{ts}.txt")
        total       = len(self.contacts)
        sent        = sum(1 for c in self.contacts if c.get("status") == "Enviado")
        failed      = sum(1 for c in self.contacts if c.get("status") == "Falha")
        pending     = total - sent - failed

        lines = [
            "=" * 65,
            f"  RELATÓRIO DE ENVIO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "=" * 65,
            f"  Total: {total}   Enviados: {sent}   Falhas: {failed}   Pendentes: {pending}",
            "-" * 65,
            f"  {'Nome':<30} {'Telefone':<20} Status",
            "-" * 65,
        ]
        for c in self.contacts:
            lines.append(f"  {c['nome']:<30} {c['telefone']:<20} {c.get('status', 'Pendente')}")
        lines.append("=" * 65)

        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"Relatório exportado: {report_path}")
        messagebox.showinfo("Relatório", f"Arquivo criado: {report_path}")

    # ──────────────────────────────────────────────────────────────────────────
    # Tabela
    # ──────────────────────────────────────────────────────────────────────────

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for item in self.contacts:
            status = item.get("status", "Pendente")
            self.tree.insert("", "end", values=(item["nome"], item["telefone"], status), tags=(status.lower(),))

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
        if not self.contacts:
            messagebox.showwarning("Aviso", "Adicione ou carregue contatos antes de iniciar.")
            return

        self.running        = True
        self.stop_requested = False
        self.paused         = False
        self.pause_btn.configure(text="⏸  Pausar")
        self.status_var.set("● Enviando mensagens...")
        self.log("Iniciando envio...")
        threading.Thread(target=self._send_all, daemon=True).start()

    def pause_send_loop(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="▶  Retomar")
            self._set_status("⏸ Pausado")
            self._log_safe("Envio pausado.")
        else:
            self.pause_btn.configure(text="⏸  Pausar")
            self._set_status("● Enviando mensagens...")
            self._log_safe("Envio retomado.")

    def stop_send_loop(self):
        self.stop_requested = True
        self._set_status("⏹ Parando envio...")
        self._log_safe("Solicitação de parada enviada.")

    def _send_all(self):
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
            self._log_safe(f"[{index + 1}/{len(self.contacts)}] Enviando para {nome} ({telefone})")

            try:
                enviar_para(nome, telefone)
                self._update_item_status(index, "Enviado")
                self._log_safe(f"[{index + 1}/{len(self.contacts)}] ✓ Concluído: {nome}")
            except Exception as exc:
                self._update_item_status(index, "Falha")
                self._log_safe(f"[{index + 1}/{len(self.contacts)}] ✗ Erro com {nome}: {exc}")

        self.running = False
        finale = "✓ Concluído" if not self.stop_requested else "⏹ Parado pelo usuário"
        self._set_status(finale)
        self._log_safe("Processo finalizado.")
        self.after(0, self._show_final_summary)

    def _show_final_summary(self):
        messagebox.showinfo("Resumo final", self.last_report)

    def _update_item_status(self, index: int, status: str):
        if index < len(self.contacts):
            self.contacts[index]["status"] = status
            self.after(0, self.refresh_table)


if __name__ == "__main__":
    app = WhatsAppPanel()
    app.mainloop()
