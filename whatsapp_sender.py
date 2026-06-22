"""Envio de mensagens usando o WhatsApp Desktop instalado no Windows.

O script lê os contatos de um CSV, valida os números, prepara os blocos de
mensagem a partir do arquivo de configuração e registra tudo no log.
"""

from __future__ import annotations

import ctypes
import csv
import logging
import os
import random
import re
import subprocess
import time
import webbrowser
from pathlib import Path

import pyautogui
import pygetwindow as gw

import config

# ── Estruturas Windows para envio de unicode via SendInput ────────────────────

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

logger = logging.getLogger("whatsapp_sender")


class InvalidPhoneNumberError(ValueError):
    """Erro levantado quando um número não atende ao formato esperado."""


class InvalidWhatsAppNumberError(RuntimeError):
    """Erro levantado quando o WhatsApp indica que o número é inválido."""


def setup_logging() -> None:
    log_path = Path(config.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8", mode="a"),
            logging.StreamHandler(),
        ],
    )
    logger.setLevel(logging.INFO)


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def validate_phone(phone: str) -> str:
    normalized = normalize_phone(phone)
    if not normalized.isdigit():
        raise InvalidPhoneNumberError(
            f"Telefone deve conter apenas números: {phone!r}"
        )

    # Aceita números brasileiros nacionais e converte para formato internacional.
    if len(normalized) in {10, 11}:
        return "55" + normalized

    if not (12 <= len(normalized) <= 15):
        raise InvalidPhoneNumberError(
            f"Telefone com tamanho inválido ({len(normalized)} dígitos): {phone!r}"
        )
    return normalized


def read_contacts(csv_path: str):
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    contacts = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV inválido: cabeçalhos não encontrados.")

        required = {"nome", "telefone"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                f"CSV inválido. Faltam colunas: {', '.join(sorted(missing))}"
            )

        for index, row in enumerate(reader, start=2):
            nome = (row.get("nome") or "").strip()
            telefone = (row.get("telefone") or "").strip()
            if not nome or not telefone:
                logger.warning("Linha %s ignorada: nome ou telefone vazio.", index)
                continue
            try:
                telefone_validado = validate_phone(telefone)
            except InvalidPhoneNumberError as exc:
                logger.warning("Linha %s ignorada para %s: %s", index, nome, exc)
                continue
            contacts.append({"nome": nome, "telefone": telefone_validado})

    return contacts


def find_whatsapp_executable() -> str | None:
    env_path = os.environ.get("WHATSAPP_EXECUTABLE")
    if env_path and Path(env_path).expanduser().exists():
        return str(Path(env_path).expanduser())

    candidates = [
        Path.home() / "AppData" / "Local" / "WhatsApp" / "WhatsApp.exe",
        Path(r"C:\Program Files\WhatsApp\WhatsApp.exe"),
        Path(r"C:\Program Files (x86)\WhatsApp\WhatsApp.exe"),
        Path(r"C:\Program Files\WindowsApps\WhatsAppDesktop_\WhatsApp.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    for base in [
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path.home() / "AppData" / "Local",
    ]:
        if base.exists():
            for match in base.rglob("WhatsApp.exe"):
                return str(match)

    return None


def open_whatsapp_desktop() -> None:
    app_path = find_whatsapp_executable()
    if not app_path:
        raise FileNotFoundError(
            "WhatsApp Desktop não encontrado. Instale o app ou informe o caminho manualmente."
        )

    subprocess.Popen([app_path])
    logger.info("WhatsApp Desktop aberto com: %s", app_path)


def wait_for_whatsapp_ready(timeout: int = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if gw.getWindowsWithTitle("WhatsApp"):
            return
        time.sleep(0.5)
    raise TimeoutError(
        "Não foi possível encontrar a janela do WhatsApp Desktop. Abra o app manualmente e tente novamente."
    )


def open_chat_direct(phone: str) -> None:
    urls = [
        f"whatsapp://send?phone={phone}",
        f"https://wa.me/{phone}",
        f"https://web.whatsapp.com/send?phone={phone}",
    ]

    for url in urls:
        try:
            if url.startswith("whatsapp://"):
                os.startfile(url)  # type: ignore[attr-defined]
            else:
                webbrowser.open(url, new=0, autoraise=True)
            logger.info("Tentando abrir conversa via: %s", url)
            # A primeira tentativa com o protocolo do app é a mais relevante.
            # Se o protocolo não abrir corretamente, o fluxo continua para os próximos.
            if url.startswith("whatsapp://"):
                time.sleep(2)
            return
        except Exception as exc:
            logger.warning("Falha ao abrir %s: %s", url, exc)

    raise RuntimeError("Não foi possível abrir o chat do WhatsApp pelo link direto.")


def focus_whatsapp_window() -> None:
    windows = gw.getWindowsWithTitle("WhatsApp")
    if not windows:
        return
    target = windows[0]
    if target.isMinimized:
        target.restore()
    target.activate()
    time.sleep(1.0)


def _click_message_input() -> None:
    """Clica no campo de mensagem do WhatsApp para garantir o foco correto."""
    windows = gw.getWindowsWithTitle("WhatsApp")
    if not windows:
        raise RuntimeError("Janela do WhatsApp nao encontrada.")
    w = windows[0]
    if w.isMinimized:
        w.restore()
        time.sleep(0.8)
    try:
        w.activate()
        time.sleep(0.5)
    except Exception:
        pass
    # Campo de mensagem fica ~60px acima da base da janela, centro horizontal
    x = w.left + w.width // 2
    y = w.top + w.height - 60
    pyautogui.click(x, y)
    time.sleep(0.5)


def _detect_and_dismiss_dialog() -> bool:
    """
    Detecta popup de numero invalido do WhatsApp via screenshot.
    O fundo do WhatsApp e escuro; um dialog e branco/claro.
    Retorna True se detectou e fechou um dialog.
    """
    windows = gw.getWindowsWithTitle("WhatsApp")
    if not windows:
        return False
    w = windows[0]
    try:
        cx = w.left + w.width // 2
        cy = w.top + w.height // 2
        shot = pyautogui.screenshot(region=(cx - 200, cy - 100, 400, 200))
        pixels = list(shot.getdata())
        light = sum(1 for r, g, b in pixels if r > 200 and g > 200 and b > 200)
        if light / len(pixels) > 0.25:
            # Dialog detectado — fecha pressionando Enter (botao OK)
            pyautogui.press("enter")
            time.sleep(0.8)
            logger.info("Dialog de numero invalido detectado e fechado.")
            return True
    except Exception:
        pass
    return False


def search_contact(name: str, phone: str) -> None:
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    pyautogui.write(name or phone)
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(1.2)


def _send_codepoint(code: int) -> None:
    """Envia um codepoint unicode via Windows SendInput (suporta emojis)."""
    if code > 0xFFFF:
        # Caractere fora do BMP: decompõe em surrogate pair
        code -= 0x10000
        _send_raw_scan(0xD800 | (code >> 10))
        _send_raw_scan(0xDC00 | (code & 0x3FF))
    else:
        _send_raw_scan(code)


def _send_raw_scan(scan: int) -> None:
    for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
        inp = _INPUT()
        inp.type = _INPUT_KEYBOARD
        inp.u.ki.wVk    = 0
        inp.u.ki.wScan  = scan
        inp.u.ki.dwFlags = flags
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def send_text(text: str) -> None:
    """
    Digita o texto caractere por caractere simulando digitação humana.
    Gera o indicador 'digitando...' no WhatsApp do destinatário e evita
    detecção de automação.
    """
    # Pausa inicial — como se estivesse pensando antes de digitar
    time.sleep(random.uniform(0.5, 1.4))

    for char in text:
        if char == "\n":
            pyautogui.hotkey("shift", "enter")
            time.sleep(random.uniform(0.2, 0.5))
            continue

        _send_codepoint(ord(char))

        # Velocidade humana varia por tipo de caractere
        if char in ".!?":
            # Pausa após fim de frase (como se estivesse relendo)
            delay = random.uniform(0.25, 0.70)
        elif char in ",;:":
            delay = random.uniform(0.12, 0.35)
        elif char == " ":
            delay = random.uniform(0.06, 0.18)
        else:
            # Velocidade de digitação normal: ~60-200 chars/min
            delay = random.uniform(0.04, 0.17)

        # Hesitação aleatória (~3% das teclas) — simula pausa de pensamento
        if random.random() < 0.03:
            delay += random.uniform(0.6, 1.8)

        time.sleep(delay)

    # Pausa antes de enviar — como se estivesse relendo a mensagem
    time.sleep(random.uniform(0.8, 2.2))
    pyautogui.press("enter")


def _copy_image_to_clipboard(image_path: str) -> None:
    abs_path = str(Path(image_path).resolve()).replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        f"$img = [System.Drawing.Image]::FromFile('{abs_path}'); "
        "[System.Windows.Forms.Clipboard]::SetImage($img); "
        "$img.Dispose()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao copiar imagem: {result.stderr.decode()}")


def send_image(image_path: str) -> None:
    _copy_image_to_clipboard(image_path)
    time.sleep(1.0)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(3.0)
    pyautogui.press("enter")
    time.sleep(1.0)


def enviar_para(nome: str, telefone: str, blocos: list | None = None,
                image_path: str | None = None,
                delay_min: float | None = None,
                delay_max: float | None = None,
                progress_callback=None) -> int:

    # 1. Abre o chat correto via link direto
    try:
        open_chat_direct(telefone)
    except RuntimeError:
        logger.warning("Falha no link direto; tentando abrir o app manualmente.")
        try:
            open_whatsapp_desktop()
        except FileNotFoundError:
            logger.warning("WhatsApp nao encontrado; aguardando abertura manual.")
        wait_for_whatsapp_ready()
        search_contact(nome, telefone)

    # 2. Aguarda o WhatsApp processar o link e navegar para o chat
    time.sleep(3.0)

    # 3. Traz o WhatsApp para frente
    focus_whatsapp_window()
    time.sleep(3.0)

    # 4. Detecta e fecha dialog de numero invalido automaticamente
    if _detect_and_dismiss_dialog():
        raise InvalidWhatsAppNumberError(
            f"Numero {telefone} nao possui WhatsApp ou e invalido."
        )

    # 5. Clica no campo de mensagem — garante que o foco esta correto
    #    (evita que o texto va parar em outra janela aberta)
    _click_message_input()

    # 6. Envia imagem se houver
    if image_path and Path(image_path).exists():
        logger.info("Enviando imagem: %s", image_path)
        send_image(image_path)

    # 7. Envia os blocos de texto com delay configurado
    if blocos is None:
        blocos = config.BLOCOS
    d_min = delay_min if delay_min is not None else config.DELAY_MIN
    d_max = delay_max if delay_max is not None else config.DELAY_MAX

    for index, bloco in enumerate(blocos):
        _click_message_input()
        texto = bloco.format(nome=nome)
        if progress_callback:
            progress_callback(index + 1, len(blocos), texto)
        send_text(texto)
        if index < len(blocos) - 1:
            delay = random.uniform(d_min, d_max)
            logger.info("Contato=%s bloco=%d/%d delay=%.1fs",
                        nome, index + 1, len(blocos), delay)
            time.sleep(delay)

    return len(blocos)


def main() -> None:
    setup_logging()
    pyautogui.FAILSAFE = True

    try:
        contatos = read_contacts(config.CSV_FILE)
    except FileNotFoundError:
        logger.error("Arquivo %s não encontrado.", config.CSV_FILE)
        print(f"Arquivo {config.CSV_FILE} não encontrado.")
        return

    if not contatos:
        logger.warning("Nenhum contato válido encontrado no CSV.")
        print("Nenhum contato válido encontrado no CSV.")
        return

    for contato in contatos:
        nome = contato["nome"]
        telefone = contato["telefone"]
        print(f"\n→ Enviando para {nome} ({telefone})")
        logger.info("Iniciando envio para %s (%s)", nome, telefone)
        try:
            blocos = enviar_para(nome, telefone)
            logger.info(
                "Sucesso: %s (%s) - %d blocos enviados",
                nome,
                telefone,
                blocos,
            )
            print(f"✓ Concluído: {nome} ({telefone})")
        except InvalidWhatsAppNumberError as exc:
            logger.warning("Pulando contato %s: %s", nome, exc)
            print(f"⚠️  Pulando {nome}: {exc}")
        except Exception as exc:
            logger.exception(
                "Erro ao enviar para %s (%s): %s",
                nome,
                telefone,
                exc,
            )
            print(f"✗ Erro com {nome} ({telefone}): {exc}")
        finally:
            time.sleep(
                random.uniform(
                    config.PAUSA_ENTRE_CONTATOS_MIN,
                    config.PAUSA_ENTRE_CONTATOS_MAX,
                )
            )

    print("\nFinalizado.")


if __name__ == "__main__":
    main()
