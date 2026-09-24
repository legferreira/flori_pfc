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

## Estrutura do projeto

```
/
├── frontend/
│   ├── index.html              # página inicial (login ou cadastro)
│   ├── cadastro.html
│   ├── login.html
│   ├── home.html               # área logada
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
│       ├── home.js
│       └── compartilhado/      # firebase.js, google-auth.js, sessao.js
├── backend/
│   ├── flori_backend/          # configurações do projeto Django
│   ├── users/
│   │   ├── models.py           # Usuario, Consentimento, Token, LogAtividade
│   │   ├── services.py         # regras de negócio (cadastro, login, senha, etc.)
│   │   ├── views.py            # camada HTTP
│   │   ├── notificacoes.py     # integração com a Brevo
│   │   ├── templates/users/emails/  # templates dos e-mails transacionais
│   │   └── migrations/
│   └── manage.py
└── README.md
```

## Como rodar localmente

### Banco de dados

MySQL instalado localmente. As tabelas são criadas pelas migrations do Django (não existe mais um script SQL manual — ele ficava desatualizado a cada mudança de model).

### Back-end

```
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install "django<6"          # requirements.txt pede 6.x; usar 5.x para compatibilidade com MySQL < 8.4
```

Copie `.env.example` para `.env` e preencha:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — conexão com o MySQL
- `BREVO_API_KEY`, `BREVO_REMETENTE_EMAIL` — envio de e-mail transacional
- `FRONTEND_URL` — usado para montar links nos e-mails
- `FIREBASE_PROJECT_ID` — login com Google (já tem valor padrão no `settings.py`)

```
python manage.py migrate
python manage.py runserver
```

### Front-end

Não precisa de instalação. Abra `frontend/index.html` num navegador, ou sirva a pasta com um servidor estático simples (ex: extensão Live Server).

## Status atual

- [x] Identidade visual definida (cores, tipografia)
- [x] Cadastro com verificação de idade mínima
- [x] Login (e-mail/senha e Google), verificação em duas etapas, redefinição de senha
- [x] Autorização por token em rota protegida
- [x] Log de auditoria
- [x] Integração com API externa (Brevo)
- [x] Páginas de Termos de Uso e Política de Privacidade
- [ ] Trilha de conteúdo educativo
- [ ] Diário do corpo e previsão de ciclo

## Autoria

Projeto desenvolvido por Leticia Ferreira, sob orientação do Prof. Bruno Messias.