# ZapFlow

ZapFlow é uma ferramenta de automação de envio de mensagens via **WhatsApp Desktop** no Windows, com painel visual moderno, leitura de contatos via CSV e suporte a geração de executável `.exe`.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![UI](https://img.shields.io/badge/UI-CustomTkinter-purple)

---

## Funcionalidades

- Painel visual dark com tema moderno (customtkinter)
- Cards de estatísticas em tempo real (Total, Enviados, Falhas, Pendentes)
- Tabela de contatos com status colorido por linha
- Barra de progresso animada
- Log de atividade em tempo real
- Adicionar contatos manualmente ou via CSV
- Remover contatos da lista
- Salvar e exportar relatório em `.txt`
- Pausar e retomar envio a qualquer momento
- Validação automática de números brasileiros e internacionais
- Suporte a emojis e acentos nas mensagens (via clipboard)
- Ícone personalizado na janela e barra de tarefas

---

## Estrutura do projeto

```
bot/
├── panel_app.py          # Painel visual principal
├── whatsapp_sender.py    # Motor de envio via WhatsApp Desktop
├── config.py             # Mensagens, delays e configurações
├── contatos.csv          # Lista de contatos (nome,telefone)
├── requirements.txt      # Dependências Python
├── img/
│   ├── zapflow.png       # Logo do app
│   └── zapflow.ico       # Ícone para o executável
└── envios.log            # Histórico de execução (gerado automaticamente)
```

---

## Como usar

### Opção 1 — Executável (recomendado)

1. Vá até a pasta `dist/`
2. Coloque o `contatos.csv` na mesma pasta que o `ZapFlow.exe`
3. Abra o `ZapFlow.exe` com duplo clique

> Para gerar o `.exe` novamente, veja a seção abaixo.

### Opção 2 — Rodar via Python

**1. Criar o ambiente virtual**
```powershell
python -m venv venv
venv\Scripts\activate
```

**2. Instalar dependências**
```powershell
pip install -r requirements.txt
```

**3. Preparar os contatos**

Edite `contatos.csv`:
```csv
nome,telefone
Maria,5511999999999
João,5511888888888
```

**4. Ajustar as mensagens**

Edite `config.py` para personalizar os blocos de texto, delays e pausas.

**5. Executar o painel**
```powershell
python panel_app.py
```

---

## Gerar o executável (.exe)

```powershell
pip install pyinstaller pillow

# Converter logo para .ico
python -c "from PIL import Image; img=Image.open('img/zapflow.png'); img.save('img/zapflow.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

# Gerar o .exe
pyinstaller --onefile --windowed --icon=img/zapflow.ico --name=ZapFlow --add-data "img;img" --add-data "config.py;." panel_app.py

# Copiar CSV para a pasta de saída
copy contatos.csv dist\contatos.csv
```

O executável ficará em `dist/ZapFlow.exe`.

---

## Requisitos

- Windows 10/11
- WhatsApp Desktop instalado e com sessão ativa
- Python 3.10+ (apenas para rodar via script)

---

## Observações

- O WhatsApp Desktop precisa estar aberto antes de iniciar o envio.
- Números inválidos são ignorados automaticamente com aviso no log.
- O envio deve ser usado com responsabilidade dentro das diretrizes da plataforma.

---

## Autor

Desenvolvido por **Dlima15**.
