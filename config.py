from pathlib import Path

# Blocos de mensagem que serão enviados. Use {nome} para personalizar.
BLOCOS = [
    "Olá! Tudo bem?\nSou Danilo Lima desenvolvedor da Zinkra.",
    "Pesquisei seu escritório no Google, do jeito que um cliente faria antes de contratar um advogado.",
    "Reparei que ainda não tem um site, o que não reflete o nível de profissionalismo e qualidade que seu perfil aqui transmite.",
    "Criamos sites para advogados que transmitem autoridade, aparecem nas primeiras posições do Google e geram consultas sem depender só de indicação.",
    "Se quiser, posso montar uma prévia gratuita de como ficaria o seu, sem compromisso nenhum.",
    "Quem seria o responsável para encaminhar a proposta?"
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
