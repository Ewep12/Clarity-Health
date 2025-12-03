🩺 Clarity Health — Monitoramento Inteligente de Glicemia com IA

Clarity Health é uma aplicação web desenvolvida em Python/Flask que permite registrar medições de glicose e realizar análise preditiva usando Machine Learning. O sistema envia alertas automáticos via Telegram para o usuário e/ou contato de confiança em caso de risco de hipoglicemia ou hiperglicemia.

Funcionalidades Principais

– Cadastro e login com autenticação JWT
– Registro de glicemia com data, sintomas e informações adicionais
– Histórico completo de medições
– Inteligência artificial com análise preditiva a partir de apenas 5 registros
– Detecção de risco em tempo real
– Notificações automáticas via Telegram
– Chat com mensagens e alerta de emergência
– API REST documentada e pronta para integrações

Inteligência Artificial

O modelo de IA utiliza:

• Regressão Ridge (scikit-learn)
• Features de atraso (lag features)
• Taxa de variação instantânea em mg/dL/min
• Previsão de glicemia em 30 minutos

O modelo é treinado automaticamente quando o usuário atinge pelo menos 5 registros válidos no banco de dados.

Arquivo responsável: analysis.py

Arquitetura do Projeto

Estrutura dos principais arquivos:

app.py – API Flask
analysis.py – IA e previsões
auth.py – Autenticação com JWT
database.py – Modelos do banco usando SQLAlchemy
glucose_model.pkl – Arquivo do modelo treinado
templates/ – Arquivos HTML
static/ – Arquivos CSS e JavaScript
add_columns.py – Script de migração
requirements.txt – Lista de dependências

Tecnologias Utilizadas

Backend: Python, Flask, SQLAlchemy, JWT, Flask-CORS
Machine Learning: scikit-learn, pandas, numpy, joblib
Banco de dados: SQLite
Integração externa: Telegram Bot API

Autenticação

Toda rota privada exige um token JWT enviado no cabeçalho Authorization usando o formato:

Authorization: Bearer SEU_TOKEN_AQUI

Endpoints Principais

Autenticação:

POST /api/register
Campos esperados: email e password

POST /api/login
Retorna: mensagem e token JWT

Registro de glicemia:

POST /api/record
Campos aceitos: valor (value), meal_time, exercise_time, symptoms

Análise inteligente:

GET /api/analyze
Retorna nível de risco, mensagem explicativa e previsão de glicemia futura

Telegram:

POST /api/user/telegram
Configura telegram_chat_id e trusted_telegram_id

Instalação e Execução

Clonar o repositório

Criar um ambiente virtual

Instalar dependências

Configurar as variáveis de ambiente

Executar a aplicação com python app.py

Acessar no navegador: http://localhost:5000

Variáveis importantes de ambiente:

SECRET_KEY
TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN

Avisos importantes

– O modelo só é treinado após 5 registros por usuário
– Para resetar a IA, basta apagar o arquivo glucose_model.pkl
– Notificações funcionam apenas com TELEGRAM_ENABLED = 1 e token de bot válido

Melhorias Futuras

– Dashboard com gráficos da evolução da glicemia
– Integração com dispositivos Bluetooth de medição
– geração de relatórios em PDF
– Múltiplos usuários por família com níveis de permissão
– Treinamento incremental do modelo

Licença

Projeto de caráter educacional e acadêmico, livre para estudo e uso não comercial.

Autores e Orientação

Construido e feito por Ewerton Pereira
Orientado por Anderson Bispo
