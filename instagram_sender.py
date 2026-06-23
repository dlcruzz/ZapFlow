"""
Envio de DMs via app do Instagram para Windows (pyautogui).
Usa o app nativo instalado via Microsoft Store — sem Chrome, sem Selenium.
"""

from __future__ import annotations

import ctypes
import logging
import os
import random
import time
from pathlib import Path

import pyautogui
import pygetwindow as gw

logger = logging.getLogger("instagram_sender")

pyautogui.FAILSAFE = False


# ─── Erros ────────────────────────────────────────────────────────────────────

class InstagramLoginError(RuntimeError):
    pass

class InstagramUserNotFound(RuntimeError):
    pass

class InstagramDMError(RuntimeError):
    pass


# ─── Win32: forçar foco ───────────────────────────────────────────────────────

def _force_focus(hwnd: int) -> None:
    user32   = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    curr     = kernel32.GetCurrentThreadId()
    target   = user32.GetWindowThreadProcessId(hwnd, None)
    if curr != target:
        user32.AttachThreadInput(curr, target, True)
    user32.ShowWindow(hwnd, 9)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if curr != target:
        user32.AttachThreadInput(curr, target, False)


def _get_instagram_window():
    wins = gw.getWindowsWithTitle("Instagram")
    return wins[0] if wins else None


def _focus_instagram_window() -> None:
    w = _get_instagram_window()
    if not w:
        return
    hwnd = ctypes.windll.user32.FindWindowW(None, "Instagram")
    if hwnd:
        _force_focus(hwnd)
    time.sleep(0.5)


# ─── Abrir app ────────────────────────────────────────────────────────────────

def abrir_app_instagram() -> None:
    """Abre o app do Instagram se não estiver aberto."""
    if _get_instagram_window():
        _focus_instagram_window()
        return
    os.startfile("instagram://")
    for _ in range(15):
        time.sleep(1)
        if _get_instagram_window():
            break
    _focus_instagram_window()
    time.sleep(2)


# ─── Navegar para perfil ──────────────────────────────────────────────────────

def _navegar_para_usuario(username: str) -> None:
    """
    Navega para o perfil de um usuário via URI scheme do app.
    instagram://user?username=XXXX abre o perfil direto no app.
    """
    username = username.lstrip("@").strip()
    _focus_instagram_window()
    time.sleep(0.5)

    # Tenta URI scheme direto
    os.startfile(f"instagram://user?username={username}")
    time.sleep(4.0)
    _focus_instagram_window()
    time.sleep(1.0)


# ─── Clicar no botão Mensagem ─────────────────────────────────────────────────

def _clicar_botao_mensagem() -> bool:
    """
    Clica no botão 'Mensagem' ou 'Enviar mensagem' no perfil.
    Tenta múltiplas posições Y pois o layout pode variar.
    Layout típico do app:
      - Foto + nome na parte de cima
      - Botões Seguir / Mensagem logo abaixo (~380-420px do topo)
    """
    w = _get_instagram_window()
    if not w:
        raise InstagramDMError("App do Instagram não encontrado.")

    # X: ~60% da largura total (botão Mensagem fica à direita do Seguir)
    x = w.left + int(w.width * 0.60)

    # Tenta diferentes posições Y
    for y_offset in [390, 375, 405, 360, 420, 440]:
        y = w.top + y_offset
        pyautogui.click(x, y)
        time.sleep(2.0)

        # Verifica se o campo de DM apareceu (campo de texto no rodapé)
        if _encontrar_input_dm(w, verificar=True):
            logger.info("Botao mensagem clicado em y=%d", y_offset)
            return True

    raise InstagramDMError(
        "Botão 'Mensagem' não encontrado no perfil.\n"
        "Verifique se você e o usuário se seguem mutuamente."
    )


# ─── Campo de texto do DM ─────────────────────────────────────────────────────

def _encontrar_input_dm(w=None, verificar: bool = False):
    """
    O campo de texto do DM fica no rodapé do chat.
    Clica nele para garantir foco.
    """
    if w is None:
        w = _get_instagram_window()
    if not w:
        return False

    x = w.left + int(w.width * 0.5)
    y = w.top + w.height - 70   # ~70px acima do rodapé

    if verificar:
        # Faz um screenshot pequeno na região do input
        # Se tiver área escura/caixa de texto, assumimos que abriu
        try:
            shot = pyautogui.screenshot(region=(w.left + 200, w.top + w.height - 120,
                                                 w.width - 300, 80))
            pixels = list(shot.getdata())
            # Área de input tem fundo mais escuro que o restante
            dark = sum(1 for r, g, b in pixels if r < 60 and g < 60 and b < 60)
            if dark / len(pixels) > 0.1:
                pyautogui.click(x, y)
                time.sleep(0.5)
                return True
        except Exception:
            pass
        return False

    pyautogui.click(x, y)
    time.sleep(0.5)
    return True


# ─── Digitar e enviar ─────────────────────────────────────────────────────────

# Estruturas Win32 para envio de unicode via SendInput
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

_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP   = 0x0002
_INPUT_KEYBOARD    = 1


def _send_char(code: int) -> None:
    if code > 0xFFFF:
        code -= 0x10000
        _send_scan(0xD800 | (code >> 10))
        _send_scan(0xDC00 | (code & 0x3FF))
    else:
        _send_scan(code)


def _send_scan(scan: int) -> None:
    for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
        inp = _INPUT()
        inp.type        = _INPUT_KEYBOARD
        inp.u.ki.wScan  = scan
        inp.u.ki.dwFlags = flags
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _digitar_texto(texto: str) -> None:
    """Digita o texto caractere por caractere (comportamento humano)."""
    time.sleep(random.uniform(0.5, 1.2))
    for char in texto:
        if char == "\n":
            pyautogui.hotkey("shift", "enter")
            time.sleep(random.uniform(0.2, 0.4))
            continue
        _send_char(ord(char))
        if char in ".!?":
            time.sleep(random.uniform(0.2, 0.6))
        elif char == " ":
            time.sleep(random.uniform(0.05, 0.15))
        else:
            time.sleep(random.uniform(0.04, 0.14))
        if random.random() < 0.03:
            time.sleep(random.uniform(0.4, 1.2))
    time.sleep(random.uniform(0.6, 1.8))
    pyautogui.press("enter")


# ─── Função principal ─────────────────────────────────────────────────────────

def enviar_instagram(
    username: str,
    messages: list[str],
    progress_callback=None,
) -> int:
    """
    Abre o perfil do usuário no app do Instagram,
    clica em Mensagem e envia os blocos de texto.
    """
    username = username.lstrip("@").strip()
    logger.info("Navegando para @%s", username)

    # 1. Garante que o app está aberto
    abrir_app_instagram()

    # 2. Navega para o perfil
    _navegar_para_usuario(username)

    # 3. Clica no botão Mensagem
    _clicar_botao_mensagem()

    # 4. Garante foco no input do DM
    w = _get_instagram_window()
    _encontrar_input_dm(w)

    # 5. Envia cada bloco
    for idx, msg in enumerate(messages, start=1):
        if progress_callback:
            progress_callback(idx, len(messages), msg)

        _focus_instagram_window()
        _encontrar_input_dm(w)
        _digitar_texto(msg)

        if idx < len(messages):
            time.sleep(random.uniform(2.0, 5.0))

    logger.info("Envio concluido para @%s (%d msgs)", username, len(messages))
    return len(messages)
