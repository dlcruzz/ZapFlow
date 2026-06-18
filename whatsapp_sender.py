"""Envio de mensagens usando o WhatsApp Desktop instalado no Windows.

O script lê os contatos de um CSV, valida os números, prepara os blocos de
mensagem a partir do arquivo de configuração e registra tudo no log.
"""

from __future__ import annotations

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
        windows = pyautogui.getWindowsWithTitle("WhatsApp")
        if windows:
            return
        time.sleep(0.5)
    raise TimeoutError(
        "Não foi possível encontrar a janela do WhatsApp Desktop. Abra o app manualmente e tente novamente."
    )


def open_chat_direct(phone: str) -> None:
    urls = [
        f"https://wa.me/{phone}",
        f"https://web.whatsapp.com/send?phone={phone}",
        f"whatsapp://send?phone={phone}",
    ]

    for url in urls:
        try:
            if url.startswith("whatsapp://"):
                os.startfile(url)  # type: ignore[attr-defined]
            else:
                webbrowser.open(url, new=0, autoraise=True)
            logger.info("Tentando abrir conversa via: %s", url)
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


def search_contact(name: str, phone: str) -> None:
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    pyautogui.write(name or phone)
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(1.2)


def send_text(text: str) -> None:
    pyautogui.write(text)
    time.sleep(0.3)
    pyautogui.press("enter")


def enviar_para(nome: str, telefone: str) -> int:
    try:
        open_chat_direct(telefone)
    except RuntimeError:
        logger.warning(
            "Falha ao abrir o chat pelo link direto; tentando abrir o app manualmente."
        )
        try:
            open_whatsapp_desktop()
        except FileNotFoundError:
            logger.warning(
                "Não foi possível abrir o WhatsApp automaticamente; aguardando abertura manual."
            )
        wait_for_whatsapp_ready()
        search_contact(nome, telefone)

    focus_whatsapp_window()
    time.sleep(5)

    for index, bloco in enumerate(config.BLOCOS):
        texto = bloco.format(nome=nome)
        send_text(texto)
        delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
        logger.info(
            "Contato=%s (%s) bloco=%d/%d delay=%.1fs",
            nome,
            telefone,
            index + 1,
            len(config.BLOCOS),
            delay,
        )
        time.sleep(delay)

    return len(config.BLOCOS)


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
