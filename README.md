# Flori Backstage

Back-end em Django e front-end estático para o cadastro de usuárias do Flori.

A regra de negócio central é a **verificação de idade mínima (13 anos)**, validada
no front-end (UX) e no back-end (segurança). O aceite dos termos é gravado como
registro datado e versionado, para atender à exigência de comprovação da LGPD.

---

## Requisitos

- **Python 3.11+** (testado em 3.14.7)
- **MySQL 8.0+** — opcional, veja [Banco de dados](#banco-de-dados)
- Git

---

## Instalação

Todos os comandos abaixo são para **PowerShell no Windows**. Para Linux/macOS, veja
[o final desta seção](#linux--macos).

### 1. Clone e entre na pasta do back-end

```powershell
git clone <url-do-repositorio>
cd flori_backstage\backend
```

### 2. Crie o ambiente virtual

```powershell
python -m venv .venv
```

### 3. Instale as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instala Django 6.1.1, django-cors-headers, python-dotenv e PyMySQL.

### 4. Configure o `.env`

```powershell
copy .env.example .env
```

Depois abra o `.env` e preencha. Veja a próxima seção para decidir o que colocar.

> O `.env` está no `.gitignore` e **nunca** deve ser commitado.

### Linux / macOS

Mesma sequência, trocando os caminhos:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

E use `./.venv/bin/python` no lugar de `.\.venv\Scripts\python.exe` daqui em diante.

---

## Banco de dados

Você tem duas opções.

### Opção A — SQLite (rápido, sem instalar nada)

Ideal para rodar o projeto e ver funcionando. No `.env`:

```env
DB_ENGINE=sqlite
```

O banco é criado como `backend/db.sqlite3` no próximo passo. Nenhuma outra
configuração é necessária.

### Opção B — MySQL (o banco oficial do projeto)

Deixe `DB_ENGINE` **em branco** e preencha o resto:

```env
DB_ENGINE=
DB_NAME=flori_db
DB_USER=root
DB_PASSWORD=sua_senha_aqui
DB_HOST=127.0.0.1
DB_PORT=3306
```

Crie o banco antes de continuar:

```powershell
mysql -u root -p < ..\schema_users.sql
```

> O `schema_users.sql` está desatualizado: não contém a tabela `consentimentos`.
> As migrations do Django criam tudo corretamente, então rode o passo seguinte
> mesmo assim.

### Aplique as migrations

Vale para as duas opções:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

---

## Rodando o projeto

São **dois terminais**, um para cada servidor.

### Terminal 1 — back-end (porta 8000)

```powershell
cd C:\caminho\para\flori_backstage\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

### Terminal 2 — front-end (porta 5500)

```powershell
cd C:\caminho\para\flori_backstage\frontend
python -m http.server 5500 --bind 127.0.0.1
```

> Rode a partir de **dentro** da pasta `frontend`. O `http.server` serve o
> diretório atual — se rodar da raiz do projeto, o `cadastro.html` dá 404 e o
> `backend/.env` fica acessível pelo navegador.

### Acesse

| Página | URL |
|---|---|
| Cadastro | http://127.0.0.1:5500/cadastro.html |
| Login | http://127.0.0.1:5500/login.html |
| Início | http://127.0.0.1:5500/index.html |

O front-end chama a API em `http://127.0.0.1:8000`, então **os dois servidores
precisam estar no ar**.

---

## API

### `POST /api/usuarios`

Cadastra uma usuária.

```json
{
  "nome": "Ana",
  "sobrenome": "Souza",
  "apelido": "ana",
  "data_nascimento": "1995-04-10",
  "email": "ana@exemplo.com",
  "celular": null,
  "senha": "senha123",
  "termos_aceitos": true
}
```

**Respostas:**

| Status | Situação |
|---|---|
| `201` | Criada — retorna `{"id": 1, "apelido": "ana"}` |
| `400` | Dados inválidos — retorna `{"mensagem": "..."}` |
| `409` | E-mail ou celular já em uso |
| `405` | Método diferente de POST |

**Regras aplicadas:** idade mínima de 13 anos, pelo menos um contato (e-mail ou
celular), senha com no mínimo 6 caracteres, aceite dos termos obrigatório.

### Teste rápido

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/usuarios -H "Content-Type: application/json" -d '{\"nome\":\"Ana\",\"sobrenome\":\"Souza\",\"apelido\":\"ana\",\"data_nascimento\":\"1995-04-10\",\"email\":\"ana@exemplo.com\",\"senha\":\"senha123\",\"termos_aceitos\":true}'
```

> Use `curl.exe`, não `curl`. No PowerShell, `curl` é um apelido para
> `Invoke-WebRequest`, que tem sintaxe diferente.

---

## Estrutura

```
flori_backstage/
├── backend/
│   ├── flori_backend/       # configuração do projeto Django
│   │   ├── settings.py
│   │   └── urls.py
│   ├── users/               # app de usuárias
│   │   ├── models.py        # Usuario e Consentimento
│   │   ├── services.py      # CadastroUsuario — regras de negócio
│   │   ├── views.py         # CadastroUsuarioView
│   │   ├── urls.py
│   │   └── migrations/
│   ├── .env                 # local, fora do git
│   ├── .env.example
│   ├── manage.py
│   └── requirements.txt
├── frontend/                # HTML, CSS e JS estáticos
│   ├── cadastro.html
│   ├── cadastro.js
│   ├── login.html
│   ├── login.js
│   └── style.css
├── schema_users.sql
└── RELATORIO_MUDANCAS.txt   # histórico das decisões técnicas
```

---

## Problemas comuns

**`O token '&&' não é um separador de instruções válido nesta versão.`**

O PowerShell 5.1 não aceita `&&`. Use linhas separadas, ou `;` para encadear.

**`ModuleNotFoundError: No module named 'django'`**

Você está usando o Python global em vez do venv. Chame `.\.venv\Scripts\python.exe`
explicitamente, ou ative o ambiente com `.\.venv\Scripts\Activate.ps1`.

**`Can't connect to MySQL server on '127.0.0.1'`**

O MySQL não está rodando ou não está instalado. Use `DB_ENGINE=sqlite` no `.env`
para rodar sem ele.

**Página de cadastro dá 404**

O `http.server` foi iniciado fora da pasta `frontend`. Veja
[Rodando o projeto](#rodando-o-projeto).

**"Não foi possível conectar ao servidor" no formulário**

O back-end não está rodando na porta 8000. Confira o Terminal 1.

**Imports do Django em amarelo no VS Code**

O editor está apontando para o Python global. Abra a paleta com `Ctrl+Shift+P`,
escolha *Python: Select Interpreter* e selecione `backend\.venv\Scripts\python.exe`.
