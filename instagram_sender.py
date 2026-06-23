"""
Envio de DMs via app do Instagram para Windows (pyautogui).
Fluxo: lupa → pesquisa → primeiro resultado → Enviar mensagem → digitar no modal.
"""

from __future__ import annotations

import ctypes
import logging
import os
import random
import time

import pyautogui
import pygetwindow as gw
import pyperclip

logger = logging.getLogger("instagram_sender")
pyautogui.FAILSAFE = False


# ─── Erros ────────────────────────────────────────────────────────────────────

class InstagramLoginError(RuntimeError):
    pass

class InstagramUserNotFound(RuntimeError):
    pass

class InstagramDMError(RuntimeError):
    pass


# ─── Win32: forçar foco na janela ────────────────────────────────────────────

def _force_focus_ig() -> None:
    """
    Traz o Instagram para o foreground sem AttachThreadInput.
    AttachThreadInput une filas de teclado e causa vazamento de eventos
    do ZapFlow para o Instagram (abre barra de pesquisa, etc.).
    """
    hwnd = ctypes.windll.user32.FindWindowW(None, "Instagram")
    if not hwnd:
        return
    ctypes.windll.user32.ShowWindow(hwnd, 9)       # SW_RESTORE
    ctypes.windll.user32.BringWindowToTop(hwnd)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def _get_win():
    wins = gw.getWindowsWithTitle("Instagram")
    return wins[0] if wins else None


def _click(w, x_pct: float, y_pct: float, wait: float = 1.0) -> None:
    """Clica em posição relativa (%) dentro da janela do Instagram."""
    x = w.left + int(w.width  * x_pct)
    y = w.top  + int(w.height * y_pct)
    _force_focus_ig()
    pyautogui.click(x, y)
    if wait > 0:
        time.sleep(wait)


# ─── Reset de estado ──────────────────────────────────────────────────────────

def _fechar_modais() -> None:
    """Pressiona Escape 3x para fechar qualquer modal/popup/DM aberto."""
    _force_focus_ig()
    for _ in range(3):
        pyautogui.press("escape")
        time.sleep(0.4)


def _ir_para_home() -> None:
    """
    Clica no ícone Home (2º ícone da sidebar) para garantir estado
    conhecido antes de cada novo contato.
    Home: x ≈ 3.4%, y ≈ 18%
    """
    w = _get_win()
    if not w:
        return
    _force_focus_ig()
    pyautogui.click(w.left + int(w.width * 0.034),
                    w.top  + int(w.height * 0.18))
    time.sleep(random.uniform(1.5, 2.5))


def _reset_estado() -> None:
    """
    Reseta o Instagram para o feed (estado inicial limpo) antes de
    cada novo contato. Garante que modais e notificações não interfiram.
    """
    _fechar_modais()
    time.sleep(0.5)
    _ir_para_home()
    logger.info("Estado resetado para home")


# ─── Abrir app ────────────────────────────────────────────────────────────────

def abrir_app_instagram() -> None:
    if _get_win():
        _force_focus_ig()
        return
    os.startfile("instagram://")
    for _ in range(15):
        time.sleep(1)
        if _get_win():
            break
    _force_focus_ig()
    time.sleep(2)


# ─── Passo 1: Clicar na lupa da sidebar ──────────────────────────────────────

def _clicar_lupa() -> None:
    """
    Clica no ícone de pesquisa (lupa) na sidebar esquerda.
    Posição: x ≈ 3.4% da largura, y ≈ 43% da altura.
    (5º ícone de cima para baixo na sidebar estreita)
    """
    w = _get_win()
    if not w:
        raise InstagramDMError("App do Instagram não encontrado.")
    logger.info("Clicando na lupa da sidebar")
    _click(w, 0.034, 0.43, wait=2.0)


# ─── Passo 2: Digitar no campo de pesquisa ───────────────────────────────────

def _pesquisar_usuario(username: str) -> None:
    """
    Clica no input de pesquisa (topo da tela após clicar na lupa)
    e digita o username.
    Input de pesquisa: x ≈ 50%, y ≈ 11%.
    """
    w = _get_win()
    logger.info("Clicando no campo de pesquisa")
    _click(w, 0.50, 0.108, wait=0.5)

    # Limpa e digita o username
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyperclip.copy(username)
    pyautogui.hotkey("ctrl", "v")
    logger.info("Username digitado: %s", username)
    time.sleep(2.5)   # aguarda resultados aparecerem


# ─── Passo 3: Clicar no primeiro resultado ────────────────────────────────────

def _clicar_primeiro_resultado() -> None:
    """
    Clica no primeiro perfil que aparece na lista de resultados.
    Primeiro resultado: x ≈ 50%, y ≈ 24%.
    """
    w = _get_win()
    logger.info("Clicando no primeiro resultado")
    _click(w, 0.50, 0.244, wait=3.0)  # aguarda perfil carregar


# ─── Passo 4: Clicar em "Enviar mensagem" ────────────────────────────────────

def _capturar_regiao_modal(w) -> list:
    """Captura pixels da região onde o modal DM aparece (lado direito)."""
    try:
        rx = w.left + int(w.width  * 0.63)
        ry = w.top  + int(w.height * 0.15)
        rw = int(w.width  * 0.35)
        rh = int(w.height * 0.72)
        return list(pyautogui.screenshot(region=(rx, ry, rw, rh)).getdata())
    except Exception:
        return []


def _regiao_mudou(antes: list, depois: list) -> bool:
    """
    Compara dois screenshots pixel a pixel.
    Se a diferença média for > 15 por canal, houve mudança visual significativa
    (o modal abriu — a região de posts foi substituída pelo painel de chat).
    """
    if not antes or not depois or len(antes) != len(depois):
        return False
    total = sum(abs(a[0]-b[0]) + abs(a[1]-b[1]) + abs(a[2]-b[2])
                for a, b in zip(antes, depois))
    avg = total / len(antes) / 3
    logger.info("Diferenca visual: %.1f (>15 = modal abriu)", avg)
    return avg > 15


def _clicar_enviar_mensagem() -> None:
    """
    Encontra e clica em 'Enviar mensagem'.
    Usa comparação de screenshot antes/depois — se a região direita mudou,
    o modal abriu. Não depende de coordenadas fixas de pixels.
    """
    w = _get_win()

    # Estado inicial da região (posts do perfil = coloridos e variados)
    estado_inicial = _capturar_regiao_modal(w)

    for y_pct in [0.50, 0.52, 0.48, 0.54, 0.46, 0.56, 0.44, 0.58, 0.60]:
        # Verifica ANTES de clicar — modal pode ter aberto na tentativa anterior
        if _regiao_mudou(estado_inicial, _capturar_regiao_modal(w)):
            logger.info("Modal detectado ANTES do clique — parando")
            return

        logger.info("Tentando 'Enviar mensagem' em y=%.2f", y_pct)
        _force_focus_ig()
        pyautogui.click(w.left + int(w.width * 0.57),
                        w.top  + int(w.height * y_pct))
        time.sleep(2.5)

        # Verifica DEPOIS do clique
        if _regiao_mudou(estado_inicial, _capturar_regiao_modal(w)):
            logger.info("Modal aberto apos clique em y=%.2f", y_pct)
            return

        # Clique errado — fecha qualquer coisa que abriu e tenta próxima posição
        pyautogui.press("escape")
        time.sleep(0.6)

    raise InstagramDMError(
        "Botao 'Enviar mensagem' nao encontrado.\n"
        "Verifique se voce e o usuario se seguem mutuamente."
    )   # aguarda modal do DM abrir


# ─── Passo 5: Clicar no input do modal e escrever ────────────────────────────

def _clicar_input_modal() -> None:
    """
    O modal de DM aparece no canto direito.
    Input 'Mensagem...': x ≈ 79%, y ≈ 93% (bem no fundo do modal).
    """
    w = _get_win()
    logger.info("Clicando no input do modal DM")
    _click(w, 0.79, 0.93, wait=0.5)


# ─── Digitação humana via Windows SendInput ───────────────────────────────────

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_uint64),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 28)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUT_UNION)]

_KF_UNICODE = 0x0004
_KF_KEYUP   = 0x0002
_KBD        = 1


def _send_char(code: int) -> None:
    if code > 0xFFFF:
        code -= 0x10000
        _raw(0xD800 | (code >> 10))
        _raw(0xDC00 | (code & 0x3FF))
    else:
        _raw(code)


def _raw(scan: int) -> None:
    for flags in (_KF_UNICODE, _KF_UNICODE | _KF_KEYUP):
        inp = _INPUT()
        inp.type         = _KBD
        inp.u.ki.wScan   = scan
        inp.u.ki.dwFlags = flags
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _digitar(texto: str) -> None:
    """
    Digita o texto letra por letra.
    Força o foco no Instagram antes de começar e durante pausas longas.
    """
    # Garante que o Instagram tem foco antes de digitar
    _force_focus_ig()
    time.sleep(random.uniform(0.5, 1.0))

    for char in texto:
        if char == "\n":
            pyautogui.hotkey("shift", "enter")
            time.sleep(random.uniform(0.2, 0.4))
            continue
        _send_char(ord(char))
        if char in ".!?":
            time.sleep(random.uniform(0.2, 0.5))
        elif char == " ":
            time.sleep(random.uniform(0.05, 0.15))
        else:
            time.sleep(random.uniform(0.04, 0.13))
        if random.random() < 0.03:
            time.sleep(random.uniform(0.4, 1.0))
            # Após pausa longa, verifica se Instagram ainda tem foco
            _force_focus_ig()
    time.sleep(random.uniform(0.6, 1.5))
    pyautogui.press("enter")


# ─── Função principal ─────────────────────────────────────────────────────────

def enviar_instagram(
    username: str,
    messages: list[str],
    progress_callback=None,
) -> int:
    """
    Fluxo completo com delays anti-bloqueio:
    1. Clica na lupa da sidebar
    2. Pesquisa o username
    3. Clica no primeiro resultado
    4. Clica em 'Enviar mensagem'
    5. Clica no input do modal e digita as mensagens
    """
    username = username.lstrip("@").strip()
    logger.info("Iniciando envio para @%s", username)

    w = _get_win()
    if not w:
        raise InstagramDMError("App do Instagram nao esta aberto.")

    # Reseta para estado limpo (fecha modais, volta ao feed)
    _reset_estado()
    time.sleep(random.uniform(1.0, 2.0))

    # Passo 1 — Lupa
    time.sleep(random.uniform(0.5, 1.0))
    _clicar_lupa()

    # Passo 2 — Pesquisar (pequena pausa antes de digitar)
    time.sleep(random.uniform(0.5, 1.2))
    _pesquisar_usuario(username)

    # Passo 3 — Primeiro resultado (pausa como se estivesse lendo os resultados)
    time.sleep(random.uniform(1.0, 2.0))
    _clicar_primeiro_resultado()

    # Passo 4 — Clica em "Enviar mensagem" (pausa como se lesse o perfil)
    time.sleep(random.uniform(1.5, 3.0))
    _clicar_enviar_mensagem()

    # Passo 5 — Clica no input da caixa de mensagem para ativá-la
    time.sleep(random.uniform(1.5, 2.5))
    _clicar_input_modal()
    time.sleep(random.uniform(0.5, 1.0))

    # Passo 6 — Digita e envia todas as mensagens
    for idx, msg in enumerate(messages, start=1):
        if progress_callback:
            progress_callback(idx, len(messages), msg)

        _force_focus_ig()
        time.sleep(random.uniform(0.6, 1.5))
        _digitar(msg)

        if idx < len(messages):
            pausa = random.uniform(4.0, 10.0)
            logger.info("Pausa entre mensagens: %.1fs", pausa)
            time.sleep(pausa)

    # Passo 7 — Volta ao Home antes do próximo contato
    logger.info("Mensagens enviadas para @%s — voltando ao Home", username)
    time.sleep(random.uniform(1.0, 2.0))
    _fechar_modais()
    _ir_para_home()

    return len(messages)
