# Flori

Aplicação web de educação menstrual voltada a adolescentes e jovens a partir de 13 anos, desenvolvida como Projeto Final de Curso (Sistemas de Informação — UMC).

## Tecnologias

- **Back-end:** Python, Django 
- **Front-end:** HTML, CSS, JavaScript, Bootstrap
- **Banco de dados:** MySQL
- **Autenticação:** e-mail e senha, ou login com Google (Firebase Authentication)
- **API externa:** Brevo (e-mail transacional: confirmação de cadastro, código de verificação, redefinição de senha)

## Funcionalidades implementadas

- Cadastro com verificação de idade mínima (13 anos), bloqueio real e não apenas visual
- Login por e-mail/senha e por conta do Google
- Verificação em duas etapas por código enviado por e-mail
- Redefinição de senha
- Rota autenticada de exemplo (`/api/perfil`), protegida por token
- Log de auditoria de cadastro, login, logout e redefinição de senha
- Páginas de Termos de Uso e Política de Privacidade, com identificador de versão vinculado ao consentimento de cada usuária
- Trilha do conhecimento: 3 assuntos com 4 cards cada (tema, explicação, exemplo e fontes), progresso salvo por usuária
- Guia rápido "Menstruei, e agora?", fora da trilha e sem contar no progresso
- Quiz final de 10 perguntas, liberado só com todos os cards concluídos, corrigido no servidor (nota mínima de 70%)
- Certificado emitido na primeira aprovação, com nome completo, carga horária de 1 hora e código de verificação
- Dashboard com o andamento geral e por assunto

## Estrutura do projeto

```
/
├── frontend/
│   ├── index.html              # página inicial (login ou cadastro)
│   ├── cadastro.html
│   ├── login.html
│   ├── home.html               # trilha do conhecimento (página inicial da área logada)
│   ├── diario.html             # diário do corpo (em breve)
│   ├── dashboard.html          # andamento na trilha
│   ├── redefinir-senha.html
│   ├── verificar-codigo.html
│   ├── termos-de-uso.html
│   ├── politica-privacidade.html
│   ├── css/                    # identidade visual, um arquivo por contexto
│   └── js/
│       ├── cadastro.js
│       ├── cadastro-google.js
│       ├── login.js
│       ├── login-google.js
│       ├── esqueci-senha.js
│       ├── redefinir-senha.js
│       ├── verificar-codigo.js
│       ├── home.js             # página da trilha: navegação, pop up, quiz, certificado
│       ├── dashboard.js
│       ├── diario.js
│       ├── trilha/             # telas.js e popup.js (só montam o HTML)
│       └── compartilhado/      # firebase.js, google-auth.js, sessao.js, area-logada.js, componentes.js
├── backend/
│   ├── flori_backend/          # configurações do projeto Django
│   │   └── api.py              # respostas JSON, leitura do corpo e autenticação por token (usado por todos os apps)
│   ├── users/
│   │   ├── models.py           # Usuario, Consentimento, Token, LogAtividade
│   │   ├── services.py         # regras de negócio (cadastro, login, senha, etc.)
│   │   ├── views.py            # camada HTTP
│   │   ├── notificacoes.py     # integração com a Brevo
│   │   ├── templates/users/emails/  # templates dos e-mails transacionais
│   │   └── migrations/
│   ├── trilha/
│   │   ├── models.py           # Trilha, Assunto, Card, Fonte, Pergunta, Opcao, ProgressoCard, TentativaQuiz, Certificado
│   │   ├── conteudo.py         # todo o texto da trilha e do quiz (edite aqui e rode carregar_trilha)
│   │   ├── services.py         # regras de negócio (progresso, correção do quiz, certificado, dashboard)
│   │   ├── serializers.py      # o que sai na resposta da API
│   │   ├── views.py            # camada HTTP
│   │   ├── admin.py            # edição do conteúdo em /admin/
│   │   ├── management/commands/carregar_trilha.py
│   │   └── migrations/
│   └── manage.py
└── README.md
```

## Como rodar localmente

### Banco de dados

O projeto usa somente MySQL 8.0 ou mais recente, em todos os ambientes, inclusive nos testes. O MariaDB do XAMPP não serve: a versão 10.4 está abaixo do mínimo exigido pelo Django.

Com o MySQL rodando, crie o banco e o usuário (troque a senha e use a mesma no `.env`):

```sql
CREATE DATABASE flori_db CHARACTER SET utf8mb4;
CREATE USER 'flori'@'localhost' IDENTIFIED BY 'troque-esta-senha';
GRANT ALL ON flori_db.* TO 'flori'@'localhost';
GRANT ALL ON test_flori_db.* TO 'flori'@'localhost';
```

O segundo `GRANT` é para `python manage.py test`, que cria e apaga o banco `test_flori_db` a cada execução.

As tabelas são criadas pelas migrations do Django (não existe mais um script SQL manual — ele ficava desatualizado a cada mudança de model).

### Back-end

```
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha:
- `SECRET_KEY`: obrigatória, longa e aleatória (o comando para gerar está no `.env.example`)
- `DEBUG`, `ALLOWED_HOSTS`: em produção, `DEBUG=False` e o domínio
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — conexão com o MySQL
- `BREVO_API_KEY`, `BREVO_REMETENTE_EMAIL` — envio de e-mail transacional
- `FRONTEND_URL` — usado para montar links nos e-mails
- `FIREBASE_PROJECT_ID` — login com Google (já tem valor padrão no `settings.py`)

```
python manage.py migrate
python manage.py carregar_trilha    # grava o conteúdo da trilha e do quiz no banco (pode rodar de novo)
python manage.py runserver
python manage.py test               # testes automatizados (precisam do MySQL rodando)
```

Para editar o conteúdo depois, altere `backend/trilha/conteudo.py` e rode `carregar_trilha` de novo (atualiza sem duplicar), ou use o painel `/admin/` (crie o acesso com `python manage.py createsuperuser`).

### Endpoints da trilha (todos exigem `Authorization: Bearer <token>`)

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/trilha` | assuntos, cards, progresso, guia rápido, estado do quiz e certificado |
| POST | `/api/trilha/cards/<id>/concluir` | marca o card como concluído (repetir não muda a data) |
| GET | `/api/trilha/quiz` | perguntas do quiz, sem a resposta certa (403 até concluir todos os cards) |
| POST | `/api/trilha/quiz` | corrige no servidor, registra a tentativa e emite o certificado se passar |
| GET | `/api/trilha/certificado` | certificado da usuária |
| GET | `/api/dashboard` | percentual geral e por assunto |

### Front-end

Não precisa de instalação. Sirva a pasta `frontend` com um servidor estático simples (ex: extensão Live Server, na porta 5500). A API é chamada em `http://127.0.0.1:8000/api` (definido em `js/compartilhado/sessao.js`).

## Status atual

- [x] Identidade visual definida (cores, tipografia)
- [x] Cadastro com verificação de idade mínima
- [x] Login (e-mail/senha e Google), verificação em duas etapas, redefinição de senha
- [x] Autorização por token em rota protegida
- [x] Log de auditoria
- [x] Integração com API externa (Brevo)
- [x] Páginas de Termos de Uso e Política de Privacidade
- [x] Trilha de conteúdo educativo, quiz, certificado e dashboard de andamento
- [ ] Diário do corpo e previsão de ciclo

## Autoria

Projeto desenvolvido por Leticia Ferreira, sob orientação do Prof. Bruno Messias.