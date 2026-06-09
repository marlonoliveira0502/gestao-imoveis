# Como publicar o sistema na internet (Render.com — GRÁTIS)

## Passo 1 – Criar conta no GitHub (5 minutos)
1. Acesse https://github.com
2. Clique em "Sign up"
3. Use seu e-mail e crie uma senha
4. Confirme o e-mail

## Passo 2 – Criar repositório e enviar os arquivos
1. No GitHub, clique no botão "+" (canto superior direito) → "New repository"
2. Nome: `gestao-imoveis`
3. Marque "Private" (privado)
4. Clique em "Create repository"
5. Na página do repositório, clique em "uploading an existing file"
6. Arraste TODOS os arquivos desta pasta (app.py, database.py, scraper.py, requirements.txt, Procfile, render.yaml) e a pasta `templates`
7. Clique "Commit changes"

## Passo 3 – Criar conta no Render.com (3 minutos)
1. Acesse https://render.com
2. Clique "Get Started for Free"
3. Faça login com sua conta GitHub
4. Autorize o Render a acessar seus repositórios

## Passo 4 – Criar o serviço web
1. No painel do Render, clique "New +" → "Web Service"
2. Selecione o repositório `gestao-imoveis`
3. Configurações:
   - Name: `gestao-imoveis`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Clique "Create Web Service"

## Passo 5 – Configurar variáveis de ambiente
No painel do Render, vá em "Environment" e adicione:
- APP_USER = marlon
- APP_PASS = (escolha uma senha forte)
- IMOB_CPF = 59711809249
- IMOB_PASS = 1Ev5Ew
- SECRET_KEY = (qualquer texto aleatório longo)

## Passo 6 – Acessar o sistema
Após 2-3 minutos de deploy, o Render fornecerá um URL como:
  https://gestao-imoveis.onrender.com

Acesse com:
- Usuário: marlon
- Senha: (a que você escolheu acima)

## Importante — Banco de dados no Render Free
O plano gratuito do Render não persiste arquivos (o SQLite é apagado a cada deploy).
Para persistência permanente, recomendo adicionar o add-on "Render PostgreSQL" 
(gratuito por 90 dias) ou atualizar para o plano Starter ($7/mês).

Alternativa gratuita permanente: Use o Railway.app com PostgreSQL grátis.
