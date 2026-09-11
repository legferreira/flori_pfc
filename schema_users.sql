-- Flori — Schema inicial: tabela users
-- Primeira tabela necessária para a regra de negócio "verificação de idade mínima no cadastro"
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS flori_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE flori_db;

CREATE TABLE IF NOT EXISTS users (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    nome              VARCHAR(100)  NOT NULL,
    sobrenome         VARCHAR(100)  NOT NULL,
    apelido           VARCHAR(50)   NOT NULL,
    data_nascimento   DATE          NOT NULL,
    email             VARCHAR(150)  UNIQUE,
    celular           VARCHAR(20)   UNIQUE,
    senha_hash        VARCHAR(255)  NOT NULL,
    termos_aceitos    BOOLEAN       NOT NULL DEFAULT FALSE,
    criado_em         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- regra de negócio: cadastro precisa de pelo menos um contato (e-mail ou celular)
    CONSTRAINT chk_contato CHECK (email IS NOT NULL OR celular IS NOT NULL)
);

-- Observações:
-- 1. A verificação de idade mínima (13 anos) NÃO fica no banco — ela é uma regra de negócio
--    aplicada na camada de back-end (Service/View), antes do INSERT. O banco só guarda o
--    resultado de um cadastro já validado.
-- 2. senha_hash guarda o hash da senha (nunca a senha em texto puro).
-- 3. termos_aceitos é obrigatório ser TRUE antes de permitir o INSERT — validar no back-end também,
--    não confiar só no default da coluna.
-- 4. Tabela chamada "users" (em inglês) em vez de "usuarias" — decisão de projeto para manter
--    linguagem neutra em relação a gênero, já que homens trans também podem menstruar e usar o app.
