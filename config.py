from pathlib import Path

# Blocos de mensagem que serão enviados. Use {nome} para personalizar.
BLOCOS = [
    "Olá {nome}, tudo bem? 👋",
    "Pesquisei o escritório no Google — do jeito que um cliente faria antes de contratar um advogado.",
    "Crio sites para escritórios de advocacia que transmitem autoridade, aparecem no Google e geram consultas novas — sem depender só de indicação.",
    "Posso apresentar uma prévia gratuita de como ficaria o site de vocês, sem compromisso nenhum.",
    "Quem seria o responsável para eu apresentar?"
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
