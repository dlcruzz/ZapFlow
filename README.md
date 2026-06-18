# ZapFlow

ZapFlow é uma solução Python para automatizar envios de mensagens via **WhatsApp Desktop** no Windows, com leitura de contatos a partir de um CSV, validação de números, registro de logs e personalização de mensagens.

## ✨ O que o projeto faz
- Lê contatos de um arquivo CSV
- Valida números brasileiros e internacionais
- Personaliza mensagens com o nome do contato
- Abre o chat do WhatsApp usando links diretos quando possível
- Registra cada etapa em um log detalhado
- Permite ajustar delays, pausas e blocos de mensagem em um arquivo de configuração

## 🧩 Estrutura do projeto
- [whatsapp_sender.py](whatsapp_sender.py): script principal responsável pelo fluxo de envio
- [config.py](config.py): configurações de mensagens, delays e arquivos usados
- [contatos.csv](contatos.csv): lista de contatos no formato `nome,telefone`
- [requirements.txt](requirements.txt): dependências necessárias
- [envios.log](envios.log): histórico das operações executadas
- [whatsapp_session](whatsapp_session): pasta para dados da sessão do WhatsApp

## 🚀 Como usar

### 1. Criar o ambiente virtual
```powershell
python -m venv venv
venv\Scripts\activate
```

### 2. Instalar dependências
```powershell
python -m pip install -r requirements.txt
```

### 3. Preparar os contatos
Edite [contatos.csv](contatos.csv) com o formato abaixo:
```csv
nome,telefone
Maria,5511999999999
João,5511888888888
```

### 4. Ajustar as mensagens
Edite [config.py](config.py) para alterar:
- blocos de texto
- tempo entre mensagens
- pausas entre contatos
- nomes dos arquivos usados

### 5. Executar o script
```powershell
python whatsapp_sender.py
```

## 🔐 Requisitos
- Windows
- WhatsApp Desktop instalado e logado
- Python 3.10+
- Dependências listadas em [requirements.txt](requirements.txt)

## 📝 Observações importantes
- O script depende da interface do WhatsApp Desktop, então o aplicativo precisa estar aberto antes da execução.
- O envio automatizado deve ser usado com responsabilidade e dentro das regras da plataforma.
- Números inválidos são ignorados automaticamente.
- Toda execução é registrada em [envios.log](envios.log).

## 🛠️ Solução de problemas
- Se o WhatsApp não abrir automaticamente, abra o app manualmente antes de rodar o script.
- Se o contato estiver incorreto, verifique o formato do número no CSV.
- Se algo falhar, consulte o log para identificar o ponto do problema.

## 📌 Licença
Este projeto é fornecido para fins educacionais e de automação pessoal. Use com responsabilidade.

## 👤 Autor
Projeto desenvolvido para automação de comunicação via WhatsApp Desktop.

