"""Envio de mensagens diretas via Instagram Web usando Selenium."""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("instagram_sender")

_WAIT = 12


class InstagramLoginError(RuntimeError):
    """Usuário não está logado no Instagram."""


class InstagramUserNotFound(RuntimeError):
    """Perfil não encontrado."""


class InstagramDMError(RuntimeError):
    """Erro ao enviar mensagem."""


# Seletores do botão "Mensagem" no perfil (múltiplos para suportar variações do IG)
_BTN_XPATHS = [
    "//button[.//div[text()='Mensagem']]",
    "//button[.//div[text()='Message']]",
    "//button[div[text()='Mensagem']]",
    "//button[div[text()='Message']]",
    "//*[@role='button'][.//span[text()='Mensagem']]",
    "//*[@role='button'][.//span[text()='Message']]",
    "//button[contains(@class,'_acan')][.//div[contains(text(),'ensagem')]]",
]

# Seletores do campo de texto no DM
_INPUT_CSS = [
    "div[aria-label='Mensagem']",
    "div[aria-label='Message']",
    "div[contenteditable='true'][tabindex='0']",
    "div[role='textbox'][contenteditable='true']",
]


def chrome_profile_padrao() -> str:
    return str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data")


def criar_driver(chrome_user_data: str | None = None,
                 profile_dir: str = "Default") -> webdriver.Chrome:
    """Cria driver Chrome usando o perfil do usuário para manter login do Instagram."""
    opts = webdriver.ChromeOptions()

    data_dir = chrome_user_data or chrome_profile_padrao()
    if Path(data_dir).exists():
        opts.add_argument(f"--user-data-dir={data_dir}")
        opts.add_argument(f"--profile-directory={profile_dir}")

    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.maximize_window()
    return driver


def verificar_login(driver: webdriver.Chrome) -> None:
    """Abre o Instagram e verifica se o usuário está logado."""
    driver.get("https://www.instagram.com/")
    time.sleep(3)
    url = driver.current_url
    if "login" in url or "accounts/login" in url:
        raise InstagramLoginError(
            "Você não está logado no Instagram.\n"
            "Abra o Chrome normalmente, faça login no Instagram e tente novamente."
        )
    logger.info("Login verificado com sucesso.")


def _abrir_dm(driver: webdriver.Chrome, username: str) -> None:
    """Navega até o perfil e clica no botão de Mensagem."""
    username = username.lstrip("@").strip()
    wait     = WebDriverWait(driver, _WAIT)

    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(random.uniform(2.5, 4.0))

    if "Page Not Found" in driver.title or "não encontrada" in driver.page_source[:500]:
        raise InstagramUserNotFound(f"Perfil @{username} não encontrado.")

    # Tenta cada seletor até encontrar o botão de Mensagem
    clicou = False
    for xpath in _BTN_XPATHS:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            btn.click()
            clicou = True
            logger.info("Botao Mensagem clicado para @%s", username)
            break
        except TimeoutException:
            continue

    if not clicou:
        raise InstagramDMError(
            f"Botão 'Mensagem' não encontrado para @{username}.\n"
            "Verifique se você e o usuário se seguem mutuamente."
        )

    time.sleep(random.uniform(2.0, 3.5))


def _digitar_e_enviar(driver: webdriver.Chrome, texto: str) -> None:
    """Digita uma mensagem no campo de DM e envia."""
    campo = None
    for css in _INPUT_CSS:
        try:
            campo = WebDriverWait(driver, _WAIT).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css))
            )
            break
        except TimeoutException:
            continue

    if campo is None:
        raise InstagramDMError("Campo de mensagem do DM não encontrado.")

    campo.click()
    time.sleep(random.uniform(0.4, 0.9))

    # Digita caractere por caractere com velocidade humana
    actions = ActionChains(driver)
    for char in texto:
        actions.send_keys(char)
        actions.pause(random.uniform(0.04, 0.15))
    actions.perform()

    time.sleep(random.uniform(0.5, 1.2))
    campo.send_keys(Keys.RETURN)
    time.sleep(random.uniform(1.5, 3.0))


def enviar_instagram(
    username: str,
    messages: list[str],
    driver: webdriver.Chrome,
    progress_callback=None,
) -> int:
    """Envia lista de mensagens para um usuário via DM do Instagram."""
    _abrir_dm(driver, username)

    for idx, msg in enumerate(messages, start=1):
        if progress_callback:
            progress_callback(idx, len(messages), msg)
        _digitar_e_enviar(driver, msg)
        if idx < len(messages):
            time.sleep(random.uniform(2.0, 5.0))

    logger.info("Envio concluido para @%s (%d mensagens)", username, len(messages))
    return len(messages)
