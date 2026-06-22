"""ZapFlow Design System — tokens centralizados."""

# ── Cores ─────────────────────────────────────────────────────────────────────
T = {
    "bg_base":      "#0A0C0B",
    "bg_surface":   "#13161A",
    "bg_elevated":  "#1A1F24",
    "bg_hover":     "#1E252C",
    "border":       "#242A30",
    "border_focus": "#1FBF5C",

    "accent":       "#1FBF5C",
    "accent_hover": "#17A34D",
    "accent_dim":   "#0A3D20",

    "success":      "#22C55E",
    "danger":       "#FF4D4D",
    "warning":      "#F5A623",
    "info":         "#3B82F6",

    "text_1":       "#F2F4F3",
    "text_2":       "#9BA3AB",
    "text_3":       "#6B7280",

    "sidebar_w":    210,
    "topbar_h":     60,
    "r_card":       12,
    "r_btn":        8,
    "r_pill":       999,
}

# ── Tipografia ────────────────────────────────────────────────────────────────
F = {
    "title":    ("Segoe UI", 22, "bold"),
    "heading":  ("Segoe UI", 16, "bold"),
    "subhead":  ("Segoe UI", 13, "bold"),
    "body":     ("Segoe UI", 13),
    "body_sm":  ("Segoe UI", 11),
    "label":    ("Segoe UI", 11),
    "label_sm": ("Segoe UI", 10),
    "mono":     ("Consolas", 12),
    "mono_sm":  ("Consolas", 10),
}

# ── Status ────────────────────────────────────────────────────────────────────
STATUS = {
    "Enviado":  T["success"],
    "Falha":    T["danger"],
    "Enviando": T["warning"],
    "Pendente": T["text_3"],
}

# ── Espaçamento (escala de 4px) ────────────────────────────────────────────────
SP = {4: 4, 8: 8, 12: 12, 16: 16, 24: 24, 32: 32, 48: 48}
