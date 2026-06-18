from pathlib import Path

# Blocos de mensagem que serão enviados. Use {nome} para personalizar.
BLOCOS = [
    "Olá {nome}, tudo bem? 👋",
    "Sou da equipe de automação, queria te apresentar rapidamente uma oportunidade.",
    "Se quiser, posso enviar mais detalhes depois.",
    "Obrigado pela atenção!",
]

# Delay aleatório entre blocos (em segundos)
DELAY_MIN = 2.0
DELAY_MAX = 4.0

# Tempo para ler o QR code na primeira execução
QR_WAIT = 30

# Arquivos usados pelo script
CSV_FILE = "contatos.csv"
LOG_FILE = "envios.log"
USER_DATA_DIR = "./whatsapp_session"

# Pausa entre contatos diferentes
PAUSA_ENTRE_CONTATOS_MIN = 5.0
PAUSA_ENTRE_CONTATOS_MAX = 12.0
