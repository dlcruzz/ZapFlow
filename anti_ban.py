"""Módulo de proteção anti-bloqueio para o ZapFlow."""

from __future__ import annotations

import json
import random
import re
from datetime import date
from pathlib import Path


# ── Spin Text ─────────────────────────────────────────────────────────────────

def parse_spin(text: str) -> str:
    """
    Resolve variações de spin text: [opção1/opção2/opção3] → escolha aleatória.
    Exemplo: "Oi [João/amigo/você], tudo [bem/bom]?" pode virar
             "Oi amigo, tudo bom?"
    """
    def _pick(match: re.Match) -> str:
        options = [o.strip() for o in match.group(1).split("/") if o.strip()]
        return random.choice(options) if options else match.group(0)

    return re.sub(r"\[([^\[\]]+)\]", _pick, text)


# ── Estatísticas diárias ──────────────────────────────────────────────────────

class DailyStats:
    """Rastreia envios diários com persistência em JSON."""

    def __init__(self, data_dir: Path):
        self._path = data_dir / "daily_stats.json"
        self._data = self._load()

    def _load(self) -> dict:
        today = str(date.today())
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if data.get("date") == today:
                    return data
            except Exception:
                pass
        # Primeiro uso hoje — preserva first_use se já existir
        first_use = today
        if self._path.exists():
            try:
                old = json.loads(self._path.read_text(encoding="utf-8"))
                first_use = old.get("first_use", today)
            except Exception:
                pass
        return {"date": today, "sent": 0, "first_use": first_use}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def sent_today(self) -> int:
        return self._data.get("sent", 0)

    @property
    def days_active(self) -> int:
        try:
            first = date.fromisoformat(self._data.get("first_use", str(date.today())))
            return max(1, (date.today() - first).days + 1)
        except Exception:
            return 1

    def can_send(self, limit: int) -> bool:
        """Retorna True se ainda há cota disponível hoje."""
        return limit <= 0 or self.sent_today < limit

    def register_send(self) -> None:
        self._data["sent"] = self.sent_today + 1
        self._save()

    def warmup_limit(self) -> int:
        """Limite recomendado baseado em quantos dias o número está ativo."""
        days = self.days_active
        if days == 1:  return 10
        if days == 2:  return 20
        if days == 3:  return 35
        if days <= 5:  return 50
        if days <= 7:  return 70
        if days <= 14: return 100
        return 200

    def status_line(self) -> str:
        return f"Dia {self.days_active} de uso — {self.sent_today} enviados hoje"


# ── Perfis de velocidade de digitação ────────────────────────────────────────

TYPING_PROFILES: dict[str, dict] = {
    "lenta": {
        "char_min": 0.10, "char_max": 0.28,
        "space_min": 0.10, "space_max": 0.25,
        "punct_min": 0.30, "punct_max": 0.80,
        "think_chance": 0.05, "think_min": 0.8, "think_max": 2.5,
        "pre_send_min": 1.2, "pre_send_max": 3.0,
    },
    "media": {
        "char_min": 0.05, "char_max": 0.16,
        "space_min": 0.06, "space_max": 0.18,
        "punct_min": 0.18, "punct_max": 0.55,
        "think_chance": 0.03, "think_min": 0.5, "think_max": 1.8,
        "pre_send_min": 0.8, "pre_send_max": 2.2,
    },
    "rapida": {
        "char_min": 0.03, "char_max": 0.09,
        "space_min": 0.04, "space_max": 0.11,
        "punct_min": 0.10, "punct_max": 0.30,
        "think_chance": 0.02, "think_min": 0.3, "think_max": 0.9,
        "pre_send_min": 0.4, "pre_send_max": 1.2,
    },
}


def get_profile(name: str) -> dict:
    """Retorna o perfil de digitação pelo nome (ou aleatório)."""
    if name == "aleatorio" or name not in TYPING_PROFILES:
        name = random.choice(list(TYPING_PROFILES.keys()))
    return TYPING_PROFILES[name]
