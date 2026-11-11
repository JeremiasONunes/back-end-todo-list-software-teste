# Manual Técnico — Todo List API

**Projeto Integrador da UC 12 — Codificação, Manutenção e Documentação de Aplicativos para Desktop**
Curso Técnico em Informática — SENAC Minas Gerais

**Versão:** 3.0.0
**Stack:** Python 3.11+ · FastAPI · SQLAlchemy · Pydantic v2
**Banco:** SQLite em desenvolvimento · PostgreSQL em produção

---

> **Sobre este documento.** É a documentação técnica de referência do projeto. Serve de
> referência para o docente preparar as aulas, de modelo para o manual que os grupos
> produzem na Aula 23 e de gabarito para validar as entregas de cada sprint.
>
> **Este manual não reproduz o código-fonte.** A versão anterior o fazia, e o resultado
> foi previsível: na primeira refatoração, o documento passou a descrever um sistema que
> não existia mais. Aqui há **trechos** apenas onde eles ensinam uma decisão — o código
> completo está no repositório, que é a única fonte que não desatualiza.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Ambientes e banco de dados](#3-ambientes-e-banco-de-dados)
4. [Instalação e execução](#4-instalação-e-execução)
5. [Estrutura de pastas](#5-estrutura-de-pastas)
6. [Modelo de dados](#6-modelo-de-dados)
7. [Contrato da API](#7-contrato-da-api)
8. [Regras de negócio](#8-regras-de-negócio)
9. [Segurança](#9-segurança)
10. [Decisões técnicas](#10-decisões-técnicas)
11. [Testes](#11-testes)
12. [Operação e implantação](#12-operação-e-implantação)
13. [Solução de problemas](#13-solução-de-problemas)
14. [Próximos passos](#14-próximos-passos)
15. [Rastreabilidade com os indicadores da UC](#15-rastreabilidade-com-os-indicadores-da-uc)

---

## 1. Visão geral

A **Todo List API** é o backend de um sistema de gerenciamento de tarefas. Não possui
interface gráfica: expõe **7 endpoints HTTP** que recebem e devolvem JSON, podendo ser
consumida por qualquer cliente — o navegador, a documentação interativa gerada pelo
framework, um script Python ou uma aplicação front-end.

### O que o sistema faz

- Cadastra usuários com senha armazenada de forma segura (hash bcrypt).
- Autentica usuários por e-mail e senha.
- Cria, lista, atualiza e remove tarefas vinculadas a um usuário.
- Filtra e ordena tarefas por status, prioridade e prazo.
- Controla automaticamente a data de conclusão de cada tarefa.

### O que o sistema deliberadamente **não** faz

Itens fora do escopo, registrados para que a ausência não seja confundida com esquecimento
(ver [seção 14](#14-próximos-passos)):

- Autenticação por token (JWT) — o login apenas confirma as credenciais.
- Verificação de dono nas operações de alteração e exclusão de tarefa.
- Recuperação de senha e confirmação de e-mail.
- Migrações de esquema versionadas.
- Interface gráfica.

---

## 2. Arquitetura

O projeto é organizado em camadas, com uma única regra de dependência: **cada camada só
conhece a de baixo**.

```
        CLIENTE (navegador, /docs, script Python, front-end)
                            │
                            │  HTTP + JSON
                            ▼
┌───────────────────────────────────────────────────────────┐
│  main.py                                                  │
│  Aplicação · CORS · rotas · tradução de erro em HTTP      │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────┐
│  routers/              (usuarios.py · tasks.py)           │
│  Recebe requisição, chama serviço, devolve resposta       │
│  Não sabe SQL. Não decide regra de negócio.               │
└──────────┬───────────────────────────────┬────────────────┘
           ▼                               ▼
┌──────────────────────┐      ┌────────────────────────────┐
│  schemas.py          │      │  dependencies.py           │
│  Contrato JSON e     │      │  Monta os objetos que a    │
│  tradução de nomes   │      │  rota recebe injetados     │
└──────────────────────┘      └────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│  services.py           Regras de aplicação                │
│  Orquestra, valida pré-condições, levanta erro de domínio │
│  Não sabe HTTP. Não escreve SQL.                          │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────┐
│  repositories.py       Acesso ao banco                    │
│  A única camada que conhece consultas                     │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────┐
│  models.py             Entidades: dados + invariantes     │
│  enums.py · exceptions.py · security.py                   │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────┐
│  database.py · config.py    Engine, sessão e ambiente     │
└───────────────────────────┬───────────────────────────────┘
                            ▼
                  ╔═════════════════════╗
                  ║  SQLite  ou  Postgres  ║
                  ╚═════════════════════╝
```

### Três consequências práticas

**As regras de negócio moram nas entidades.** A RN-03 não está em nenhuma rota: está nos
métodos `concluir` e `reabrir` da `Tarefa`, que são o único caminho para mudar o status.
Não existe forma de deixar uma tarefa em estado inconsistente a partir de fora.

**O domínio não conhece HTTP.** Serviços e modelos levantam exceções próprias; `main.py`
as traduz em código de status. Os mesmos serviços funcionariam em um programa de terminal
— e é essa propriedade que permite testar as regras sem subir a aplicação.

**Trocar de banco não toca no código.** SQLite e PostgreSQL diferem em uma variável de
ambiente e em algumas opções de conexão, todas concentradas em `database.py`.

### Fluxo de uma requisição

Exemplo: `PATCH /tasks/7` com corpo `{"status": "concluida"}`.

| # | Onde | O que acontece |
|---|---|---|
| 1 | FastAPI | Identifica a rota e extrai `tarefa_id = 7` |
| 2 | `schemas.py` | Valida o corpo contra `TarefaUpdate`. Status inválido → **422**, sem chegar à rota |
| 3 | `dependencies.py` | Monta `TarefaServico` com os repositórios e a sessão do banco |
| 4 | `routers/tasks.py` | Converte o corpo em `AlteracoesDaTarefa` e chama o serviço |
| 5 | `services.py` | Busca a tarefa; se não existir, levanta `TarefaNaoEncontrada` |
| 6 | `models.py` | `definir_status` aplica a RN-03 — conclui, reabre ou preserva a data |
| 7 | `repositories.py` | Persiste e sincroniza o objeto com o banco |
| 8 | `schemas.py` | Converte a entidade em `TarefaOut`, traduzindo os nomes para camelCase |
| 9 | `database.py` | O `finally` de `obter_sessao` fecha a sessão — sempre |

Se o passo 5 levantar a exceção, o tratador de `main.py` a converte em **404** e os
passos seguintes não acontecem.

---

## 3. Ambientes e banco de dados

A aplicação usa um banco diferente em cada ambiente, escolhido por **uma única variável
de ambiente**.

| Ambiente | Banco | Como é escolhido |
|---|---|---|
| Desenvolvimento | SQLite em arquivo (`todo_list.db`) | padrão, sem configuração |
| Produção | PostgreSQL | `DATABASE_URL` |
| Testes | SQLite em memória | a suíte define a variável |

### Opções de conexão por dialeto

Concentradas em `_opcoes_do_engine`, em `database.py`:

| Banco | Opções | Por quê |
|---|---|---|
| SQLite em memória | `StaticPool` + `check_same_thread=False` | o banco existe só enquanto a conexão existir; sem pool estático, cada operação encontraria um banco vazio |
| SQLite em arquivo | `check_same_thread=False` | o servidor atende requisições em threads diferentes da que abriu a conexão |
| PostgreSQL | `pool_pre_ping=True` + `pool_recycle=1800` | conexão derrubada por inatividade é o erro mais comum em banco gerenciado |

### Normalização da URL

Plataformas de hospedagem entregam a URL do PostgreSQL começando com `postgres://`, que o
SQLAlchemy 2 não aceita mais. A aplicação corrige o esquema e resolve o driver, de modo
que a URL possa ser colada como vem:

| URL recebida | URL usada |
|---|---|
| `postgres://u:s@host/banco` | `postgresql+psycopg://u:s@host/banco` |
| `postgresql://u:s@host/banco` | `postgresql+psycopg://u:s@host/banco` |
| `postgresql+psycopg2://u:s@host/banco` | inalterada — driver explícito é respeitado |
| `sqlite:///./todo_list.db` | inalterada |

### Chave estrangeira no SQLite

O SQLite vem com a verificação de chave estrangeira **desligada** por padrão, por
compatibilidade histórica. A aplicação a liga em cada conexão:

```python
@event.listens_for(Engine, "connect")
def _ativar_chaves_estrangeiras(conexao_dbapi, _registro):
    if isinstance(conexao_dbapi, sqlite3.Connection):
        cursor = conexao_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

Sem esse ajuste, o banco de desenvolvimento aceitaria uma tarefa apontando para um
usuário inexistente, e o PostgreSQL recusaria a mesma operação em produção. Divergência
silenciosa de comportamento entre ambientes é a categoria de defeito mais caro de
encontrar: o teste passa na máquina de quem escreveu e falha depois do deploy.

O `isinstance` garante que o comando só vai a conexões SQLite; com PostgreSQL, a função
não faz nada. Há teste automatizado para o comportamento
([seção 11](#11-testes)).

### Variáveis de ambiente

`DATABASE_URL` é **obrigatória**; as demais são opcionais. O `.env.example` já vem com a
`DATABASE_URL` ativa, de modo que copiá-lo para `.env` resulta em um projeto que roda.

| Variável | Para quê | Padrão |
|---|---|---|
| `DATABASE_URL` | Banco de dados a usar | **nenhum** — ausente, a aplicação recusa subir |
| `ORIGENS_PERMITIDAS` | Origens liberadas no CORS, separadas por vírgula | `localhost:5173` e `127.0.0.1:5173` |
| `ECHO_SQL` | Imprime no terminal todo SQL gerado pelo ORM | desligado |

---

## 4. Instalação e execução

### Pré-requisitos

| Item | Versão | Para quê |
|---|---|---|
| Python | 3.11 ou superior | Executar a aplicação e os testes |
| Git | qualquer | Versionamento |
| PostgreSQL | 14 ou superior | **Somente em produção** |

Para desenvolver, Python é o único requisito: o SQLite vem na biblioteca padrão.

### Passos

```bash
git clone <url-do-repositorio>
cd todo-list-backend

python -m venv venv
venv\Scripts\Activate.ps1          # Windows (PowerShell)
# source venv/bin/activate         # Linux / macOS

pip install -r requirements.txt
uvicorn app.main:app --reload
```

O `.env` é necessário, porque `DATABASE_URL` não tem valor padrão:

```bash
cp .env.example .env                  # Linux / macOS
Copy-Item .env.example .env           # Windows (PowerShell)
```

O exemplo já vem com a `DATABASE_URL` apontando para SQLite, então não há o que editar
para rodar localmente. Na primeira execução, o arquivo `todo_list.db` é criado na raiz do
projeto com as tabelas prontas.

> O `uvicorn` roda a partir da **raiz do projeto**, não de dentro de `app/`. No lugar
> errado, o Python não encontra o pacote e responde `ModuleNotFoundError: No module
> named 'app'`.

| Endereço | O que é |
|---|---|
| `http://localhost:8000/` | Rota raiz — confirma que a API está no ar |
| `http://localhost:8000/docs` | Swagger UI — documentação interativa e painel de testes |
| `http://localhost:8000/redoc` | ReDoc — a mesma documentação em formato de leitura |
| `http://localhost:8000/openapi.json` | Contrato da API em formato OpenAPI |

---

## 5. Estrutura de pastas

```
todo-list-backend/
├── app/
│   ├── main.py               # aplicação, CORS, rotas e tradução de erros em HTTP
│   ├── config.py             # Configuracao imutável; escolha do banco por URL
│   ├── database.py           # engine, sessão, Base e os ajustes por dialeto
│   ├── enums.py              # StatusTarefa, PrioridadeTarefa, CampoOrdenacao, Ordem
│   ├── exceptions.py         # hierarquia de exceções de domínio
│   ├── models.py             # Usuario e Tarefa — dados + comportamento
│   ├── schemas.py            # contrato JSON e tradução snake_case ↔ camelCase
│   ├── security.py           # HashDeSenha (interface) e HashBcrypt
│   ├── tempo.py              # agora_utc() e a coluna DataHoraUTC
│   ├── tokens.py             # emissão e leitura do token JWT
│   ├── validacao.py          # mensagens de validação do Pydantic em pt-BR
│   ├── repositories.py       # RepositorioBase (ABC) + repositórios concretos
│   ├── services.py           # UsuarioServico e TarefaServico
│   ├── dependencies.py       # montagem dos objetos injetados nas rotas
│   └── routers/
│       ├── usuarios.py
│       └── tasks.py
├── tests/
│   ├── conftest.py           # SQLite em memória e hash instantâneo
│   ├── test_dominio.py       # 37 testes — regras de negócio, sem banco e sem HTTP
│   ├── test_configuracao.py  # 25 testes — escolha do banco e normalização da URL
│   ├── test_seguranca.py     # 12 testes — contrato de hash e o HashBcrypt real
│   ├── test_banco.py         #  7 testes — chaves estrangeiras e unicidade
│   ├── test_api.py           # 31 testes — endpoints e contrato JSON
│   ├── test_autenticacao.py  # 34 testes — token, 401/403 e isolamento
│   └── test_integracao_frontend.py  # 34 testes — o contrato com o front-end
├── docs/
│   ├── manual_tecnico.md     # este documento
│   └── roteiro-de-construcao-7-dias.md
├── cliente_teste.py          # script da Aula 21 (consome a API, aplica algoritmos)
├── pytest.ini
├── requirements.txt
├── .env.example
└── .gitignore
```

### `.gitignore`

```gitignore
.env
venv/
__pycache__/
*.pyc
.vscode/
.pytest_cache/
*.db
*.db-journal
*.sqlite3
```

Dois itens que costumam faltar: o `*.db`, porque o banco de desenvolvimento é arquivo de
trabalho local e versionado geraria conflito em todo `pull`; e o `.pytest_cache/`, criado
pela suíte a cada execução.

---

## 6. Modelo de dados

### Diagrama de relacionamento

```
┌─────────────────────────┐              ┌──────────────────────────┐
│        usuarios         │              │         tarefas          │
├─────────────────────────┤              ├──────────────────────────┤
│ PK  id                  │──┐           │ PK  id                   │
│     nome                │  │           │ FK  usuario_id           │
│ UQ  email               │  └──── 1:N ──│     titulo               │
│     senha_hash          │              │     status               │
│     criado_em           │              │     prioridade           │
└─────────────────────────┘              │     prazo                │
                                         │     criado_em            │
                                         │     atualizado_em        │
                                         │     concluido_em         │
                                         └──────────────────────────┘

Um usuário possui muitas tarefas. Toda tarefa pertence a exatamente um usuário.
```

### Dicionário de dados — `usuarios`

| Coluna | Atributo Python | Tipo | Nulo | Chave | Descrição |
|---|---|---|---|---|---|
| `id` | `id` | INTEGER / SERIAL | Não | PK | Identificador único |
| `nome` | `nome` | VARCHAR(120) | Não | — | Nome do usuário; recusa texto vazio |
| `email` | `email` | VARCHAR(180) | Não | UNIQUE | Identifica o usuário no login; gravado normalizado |
| `senha_hash` | `_senha_hash` | VARCHAR(255) | Não | — | Hash bcrypt. **Privado e nunca exposto pela API** |
| `criado_em` | `criado_em` | DATETIME / TIMESTAMP | Não | — | Data e hora do cadastro |

### Dicionário de dados — `tarefas`

| Coluna | Atributo Python | Tipo | Nulo | Chave | Descrição |
|---|---|---|---|---|---|
| `id` | `id` | INTEGER / SERIAL | Não | PK | Identificador único |
| `usuario_id` | `usuario_id` | INTEGER | Não | FK → `usuarios.id` | Dono da tarefa |
| `titulo` | `titulo` | VARCHAR(200) | Não | — | Descrição curta; recusa vazio e remove espaços das pontas |
| `status` | `status` (somente leitura) | VARCHAR(20) | Não | — | `pendente` ou `concluida`. Alterável só por `concluir`/`reabrir` |
| `prioridade` | `prioridade` | VARCHAR(20) | Não | — | `baixa`, `media`, `alta` ou `urgente` |
| `prazo` | `prazo` | DATE | Sim | — | Data limite, opcional |
| `criado_em` | `criado_em` | DATETIME / TIMESTAMP | Não | — | Data de criação, em UTC |
| `atualizado_em` | `atualizado_em` | DATETIME / TIMESTAMP | Não | — | Atualizado automaticamente a cada alteração, em UTC |
| `concluido_em` | `concluido_em` (somente leitura) | DATETIME / TIMESTAMP | Sim | — | Gerido pela RN-03, em UTC |

As três colunas de data e hora usam o tipo `DataHoraUTC` (`app/tempo.py`): gravam em UTC
sem fuso — formato que SQLite e PostgreSQL tratam igual — e devolvem o valor já com o
fuso declarado. Ver [D-12](#d-12--datas-sempre-em-utc-declarado).

Três atributos não são livremente atribuíveis de fora da entidade — `_senha_hash`,
`status` e `concluido_em`. Essa restrição é o que transforma as regras de negócio em
invariantes: não existe caminho que as burle.

### Índices

| Índice | Tabela | Coluna | Único |
|---|---|---|---|
| `ix_usuarios_email` | usuarios | email | Sim |
| `ix_usuarios_id` | usuarios | id | Não |
| `ix_tarefas_usuario_id` | tarefas | usuario_id | Não |
| `ix_tarefas_id` | tarefas | id | Não |

O índice único em `email` é a garantia da RN-01 no nível do banco. O índice em
`usuario_id` existe porque **toda** listagem de tarefas filtra por ele.

### DDL gerado

Os modelos são portáveis entre os dois bancos sem nenhuma alteração. O SQLAlchemy gera o
dialeto correto a partir das mesmas classes.

**SQLite (desenvolvimento)**

```sql
CREATE TABLE usuarios (
    id          INTEGER      NOT NULL,
    nome        VARCHAR(120) NOT NULL,
    email       VARCHAR(180) NOT NULL,
    senha_hash  VARCHAR(255) NOT NULL,
    criado_em   DATETIME     NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE tarefas (
    id             INTEGER      NOT NULL,
    usuario_id     INTEGER      NOT NULL,
    titulo         VARCHAR(200) NOT NULL,
    status         VARCHAR(20)  NOT NULL,
    prioridade     VARCHAR(20)  NOT NULL,
    prazo          DATE,
    criado_em      DATETIME     NOT NULL,
    atualizado_em  DATETIME     NOT NULL,
    concluido_em   DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);
```

**PostgreSQL (produção)**

```sql
CREATE TABLE usuarios (
    id          SERIAL       NOT NULL,
    nome        VARCHAR(120) NOT NULL,
    email       VARCHAR(180) NOT NULL,
    senha_hash  VARCHAR(255) NOT NULL,
    criado_em   TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE tarefas (
    id             SERIAL       NOT NULL,
    usuario_id     INTEGER      NOT NULL,
    titulo         VARCHAR(200) NOT NULL,
    status         VARCHAR(20)  NOT NULL,
    prioridade     VARCHAR(20)  NOT NULL,
    prazo          DATE,
    criado_em      TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    atualizado_em  TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    concluido_em   TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);
```

Não é preciso executar esse SQL à mão: `criar_tabelas()` o faz na subida da aplicação.
Está aqui como referência e para conferência do que existe no banco.

---

## 7. Contrato da API

### Resumo dos endpoints

| # | Método | Caminho | Descrição | Sucesso |
|---|---|---|---|---|
| 1 | `POST` | `/usuarios` | Cadastra um usuário | 201 |
| 2 | `POST` | `/usuarios/login` | Autentica por e-mail e senha | 200 |
| 3 | `GET` | `/usuarios/{usuario_id}` | Busca um usuário por ID | 200 |
| 4 | `POST` | `/tasks` | Cria uma tarefa | 201 |
| 5 | `GET` | `/tasks` | Lista tarefas de um usuário, com filtros | 200 |
| 6 | `PATCH` | `/tasks/{tarefa_id}` | Atualiza campos de uma tarefa | 200 |
| 7 | `DELETE` | `/tasks/{tarefa_id}` | Remove uma tarefa | 204 |

### Códigos de status

| Código | Significado | Quando ocorre |
|---|---|---|
| `200 OK` | Sucesso | Consulta ou atualização bem-sucedida |
| `201 Created` | Recurso criado | Cadastro de usuário ou tarefa |
| `204 No Content` | Sucesso sem corpo | Exclusão de tarefa |
| `401 Unauthorized` | Credenciais inválidas | Login com e-mail ou senha errados |
| `404 Not Found` | Recurso inexistente | ID de usuário ou tarefa que não existe |
| `409 Conflict` | Conflito de estado | Cadastro com e-mail já usado |
| `422 Unprocessable Entity` | Dados inválidos | Validação do Pydantic, ou regra de negócio violada |

### Nomenclatura dos campos

O JSON usa **camelCase** (`usuarioId`, `criadoEm`, `concluidoEm`); o Python usa
`snake_case`. A tradução acontece nos schemas, na borda da aplicação. Na **entrada**, as
duas formas são aceitas.

### Formato dos erros

Toda resposta de erro tem `detail` como **uma frase em português**:

```json
{ "detail": "E-mail já cadastrado." }
```

Isso vale também para os 422 de validação, que por padrão no FastAPI trazem `detail`
como uma lista de objetos. Um cliente que exibe a mensagem na tela mostraria
`[object Object]`; e quem consome teria de tratar dois formatos no mesmo campo. A lista
original continua disponível em `erros`, que é o que serve para depurar e para destacar
o campo errado em um formulário:

```json
{
  "detail": "nome: deve ter no mínimo 2 caracteres. | email: e-mail inválido.",
  "erros": [ { "type": "string_too_short", "loc": ["body", "nome"], "…": "…" } ]
}
```

As mensagens de validação são traduzidas em `app/validacao.py`. A tabela cobre os tipos
de erro que os campos desta API podem produzir — não o catálogo inteiro do Pydantic — e
o que não estiver mapeado cai na mensagem original: é melhor uma frase em inglês do que
uma genérica que não diz qual é o problema.

### 1. `POST /usuarios`

```json
{ "nome": "Ana Souza", "email": "ana@exemplo.com", "senha": "senha123" }
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `nome` | string | Sim | 2 a 120 caracteres |
| `email` | string | Sim | Formato válido, único no sistema |
| `senha` | string | Sim | 6 a 72 caracteres (72 é o limite do bcrypt) |

**201 Created**

```json
{
  "id": 1,
  "nome": "Ana Souza",
  "email": "ana@exemplo.com",
  "criadoEm": "2026-10-05T14:32:35.833782"
}
```

A senha não aparece na resposta: o schema de saída não a declara.

**Erros:** `409` e-mail já cadastrado (RN-01); `422` e-mail malformado, senha curta ou
campo ausente.

### 2. `POST /usuarios/login`

```json
{ "email": "ana@exemplo.com", "senha": "senha123" }
```

**200 OK** — mesmo formato do cadastro.
**401** — `{"detail": "E-mail ou senha inválidos."}` tanto para e-mail inexistente quanto
para senha errada. A mensagem é idêntica de propósito: informar que o e-mail não existe
revelaria quais endereços estão cadastrados.

### 3. `GET /usuarios/{usuario_id}`

**200 OK** — dados públicos do usuário. **404** se não existir.

### 4. `POST /tasks`

```json
{ "usuarioId": 1, "titulo": "Entregar o relatório", "prioridade": "alta", "prazo": "2026-12-20" }
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `usuarioId` | inteiro | Sim | Deve existir |
| `titulo` | string | Sim | 1 a 200 caracteres, não vazio |
| `prioridade` | string | Não | `baixa`\|`media`\|`alta`\|`urgente`. Padrão `media` |
| `prazo` | data | Não | `AAAA-MM-DD`, pode ser nulo |

**201 Created**

```json
{
  "id": 1,
  "usuarioId": 1,
  "titulo": "Entregar o relatório",
  "status": "pendente",
  "prioridade": "alta",
  "prazo": "2026-12-20",
  "criadoEm": "2026-10-05T14:32:35.842926",
  "atualizadoEm": "2026-10-05T14:32:35.842927",
  "concluidoEm": null
}
```

O `status` **não** é aceito na criação: toda tarefa nasce pendente (RN-02). Quem decide
isso é o servidor.

**Erros:** `404` usuário inexistente (RN-04); `422` prioridade fora da lista, título
vazio ou data malformada.

### 5. `GET /tasks`

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `usuarioId` | inteiro | **Sim** | — | Dono das tarefas |
| `status` | string | Não | — | `pendente`, `concluida` ou `todas` (sem filtro) |
| `prioridade` | string | Não | — | Nível de prioridade, ou `todas` |
| `prazoAte` | data | Não | — | Só tarefas com prazo até esta data |
| `busca` | string | Não | — | Filtra pelo título, sem diferenciar maiúsculas |
| `ordenarPor` | string | Não | `criadoEm` | `criadoEm` (ou `recente`), `prazo`, `prioridade` |
| `ordem` | string | Não | ordem natural do campo | `asc` ou `desc` |
| `limit` | inteiro | Não | `50` | Máximo de resultados (1 a 200) |
| `offset` | inteiro | Não | `0` | Registros a pular |

```http
GET /tasks?usuarioId=1&status=pendente&ordenarPor=prioridade
```

**200 OK** — lista de tarefas. Array vazio `[]` quando nada corresponde: a coleção
existe, apenas está vazia — não é 404.

O cabeçalho **`X-Total-Count`** traz quantas tarefas atendem ao filtro, ignorando `limit`
e `offset`. Vai no cabeçalho, e não no corpo, porque trocar o array por
`{"total": …, "itens": […]}` quebraria todo cliente que já o consome como array.

Ordenar por `prioridade` segue a ordem semântica (urgente, alta, media, baixa), e não a
alfabética. Valor inválido em `ordenarPor` devolve **422**, e não uma ordenação
silenciosamente trocada.

Quatro comportamentos da listagem que não são óbvios:

| Comportamento | Por quê |
|---|---|
| Omitir `ordem` usa o **sentido natural** do campo: `criadoEm` decrescente, `prazo` e `prioridade` crescentes | Um padrão único acertaria em um campo e erraria em dois — decrescente por prazo mostraria primeiro o que vence por último |
| Tarefa **sem prazo vai para o fim** nos dois sentidos | Sem `NULLS LAST` explícito o resultado dependeria do banco: o SQLite trata `NULL` como o menor valor, o PostgreSQL o posiciona de forma diferente em cada sentido |
| `status=todas` e `prioridade=todas` valem como **sem filtro** | É o valor inicial dos seletores do front-end, que o envia em vez de omitir o parâmetro |
| `ordenarPor=recente` é **apelido** de `criadoEm` | Mesmo critério com dois nomes: o cliente nomeia o resultado, a API nomeia a coluna |

A busca é feita no servidor, e não no cliente, porque é o que a torna correta junto com a
paginação: filtrar no cliente alcançaria apenas a página já recebida. O termo é tratado
como texto literal — `%` e `_`, que são curingas do `LIKE`, são escapados antes de chegar
ao SQL.

### 6. `PATCH /tasks/{tarefa_id}`

Atualização **parcial**: envie apenas os campos que mudaram.

```json
{ "status": "concluida" }
```

| Campo | Tipo | Regra |
|---|---|---|
| `titulo` | string | 1 a 200 caracteres |
| `status` | string | `pendente` ou `concluida` |
| `prioridade` | string | `baixa`\|`media`\|`alta`\|`urgente` |
| `prazo` | data ou `null` | `AAAA-MM-DD` |

**200 OK** — a tarefa completa e atualizada, com `concluidoEm` ajustado conforme a RN-03.

Campo **ausente** e campo enviado como **`null`** são tratados de forma diferente: não
mencionar o prazo o mantém; enviar `"prazo": null` o apaga.

**Erros:** `404` tarefa inexistente; `422` valor fora das opções ou título vazio.

> **Por que `PATCH` e não `PUT`?** A operação mais comum é marcar uma tarefa como
> concluída — alteração de um único campo. `PUT` exigiria reenviar o recurso completo.

### 7. `DELETE /tasks/{tarefa_id}`

**204 No Content**, sem corpo. **404** se a tarefa não existir.

### Alinhamento com o front-end React

Esta API é o backend do front-end em `todo-list-main/` (React + Vite). Os 7 endpoints
correspondem **um a um** às 7 funções que `taskService.js` e `usuarioService.js` já
chamam hoje contra o `localStorage`:

| Função do mock, hoje | Endpoint correspondente | Muda na integração? |
|---|---|---|
| `usuarioService.criar(dados)` | `POST /usuarios` | Passa a receber token na resposta |
| `usuarioService.verificarCredenciais(email, senha)` | `POST /usuarios/login` | Idem; e traduz 401 em `null` |
| `usuarioService.buscarPorId(id)` | `GET /usuarios/eu` | **Sim** — não se informa mais o id |
| `taskService.listarPorUsuario(usuarioId)` | `GET /tasks` | **Sim** — não se informa mais o dono |
| `taskService.criar(dados)` | `POST /tasks` | **Sim** — sem `usuarioId` no corpo |
| `taskService.atualizar(id, dadosParciais)` | `PATCH /tasks/{tarefa_id}` | Só o cabeçalho |
| `taskService.remover(id)` | `DELETE /tasks/{tarefa_id}` | Só o cabeçalho |

O contrato entre os dois lados não está escrito no código de nenhum deles — vive no
formato do JSON e no vocabulário dos parâmetros. Por isso é verificado como teste, em
`tests/test_integracao_frontend.py`: renomear `criadoEm` para `criado_em`, ou acrescentar
um valor ao enum de ordenação, passaria por toda a suíte sem falhar e quebraria a
integração apenas na hora de ligar as duas pontas.

**Um ponto do contrato não é tradução direta.** No front, credencial errada não é
exceção: `verificarCredenciais` devolve `null` e quem chamou decide a mensagem. Aqui é
**401**, porque é o código que descreve o que aconteceu. A conversão fica do lado do
cliente — registrada aqui para que a diferença seja deliberada.

### A integração ainda não aconteceu

**O front-end continua mockado no `localStorage`.** Ele não envia `Authorization` em
chamada alguma, e por isso, apontado para esta API sem alteração, teria todas as telas de
tarefas respondendo 401.

Isso é uma dessincronia deliberada, e vale ser explícita: até a versão 2.2.0 esta API não
exigia token *justamente* para não quebrar aquele front-end. A versão 3.0.0 passou a
exigir, fechando a falha de autorização descrita na [seção 9](#9-segurança), e a
atualização do cliente ficou para a Fase 9 do roteiro dele.

O que a integração vai exigir do lado do cliente está listado no `README.md`, seção
"Estado da integração". Em resumo: guardar o token em vez do id, anexar o cabeçalho,
rehidratar por `GET /usuarios/eu`, parar de enviar `usuarioId` e encerrar a sessão quando
a API responder 401.

**Por que os testes de contrato continuam valendo.** `tests/test_integracao_frontend.py`
verifica nomes de campos, formato das datas e vocabulário dos filtros — tudo que o
front-end mockado **já** produz e consome, e que a integração não deveria precisar
mudar. Eles travam a parte do contrato que está pronta, para que ela não se mova
enquanto a outra parte espera.

---

## 8. Regras de negócio

O que distingue esta versão da anterior não é a lista de regras, mas **onde cada uma
vive**. Regra implementada na entidade não pode ser contornada; regra implementada na
rota vale apenas para aquele endpoint.

| Regra | Descrição | Onde é garantida |
|---|---|---|
| **RN-01** | Um e-mail não pode ser usado por dois usuários | `UsuarioServico.cadastrar` (mensagem clara) + índice `UNIQUE` no banco (garantia real) |
| **RN-02** | Toda tarefa é criada pendente e sem data de conclusão | Construtor de `Tarefa` — o status não é parâmetro |
| **RN-03** | Gestão automática da data de conclusão | `Tarefa.concluir` e `Tarefa.reabrir` — único caminho para mudar o status |
| **RN-04** | Toda tarefa pertence a um usuário existente | `TarefaServico.criar` + chave estrangeira no banco |
| **RN-05** | A senha nunca é armazenada nem exposta em texto puro | `Usuario.definir_senha` + o schema de saída não declara o campo |

### RN-01 em detalhe

A verificação no serviço existe para dar uma mensagem útil (`409` com texto claro); a
constraint no banco existe porque é a única garantia real — a aplicação pode ter defeito,
o banco não permite a duplicata.

O e-mail é **normalizado** antes de gravar e de comparar (`strip` + minúsculas).
`"  ANA@Exemplo.com "` e `"ana@exemplo.com"` são o mesmo endereço; sem a normalização, a
regra deixaria passar duplicatas que diferem apenas em espaços ou maiúsculas.

### RN-03 em detalhe

| Transição | Efeito sobre `concluido_em` |
|---|---|
| `pendente` → `concluida` | Recebe a data e hora do momento da conclusão |
| `concluida` → `pendente` | Volta a ser nulo — a tarefa foi reaberta |
| `concluida` → `concluida` | **Não muda** — preserva a data da primeira conclusão |
| Alteração que não envolve status | Não muda |

```python
def concluir(self, agora: datetime | None = None) -> None:
    if self.status is StatusTarefa.CONCLUIDA:
        return                                    # preserva a data original
    self._status = StatusTarefa.CONCLUIDA.value
    self._concluido_em = agora or datetime.now()
```

O terceiro caso é o mais fácil de errar. Se o código apenas atribuísse a data sempre que
recebesse `status: "concluida"`, editar o título de uma tarefa antiga falsificaria a data
de conclusão. O parâmetro `agora` existe para que o teste possa fixar o instante e provar
que a data não mudou.

---

## 9. Segurança

### O que está implementado

| Proteção | Como |
|---|---|
| **Senha nunca em texto puro** | `bcrypt` com custo 12 e salt aleatório por senha (RN-05) |
| **Hash privado no modelo** | A coluna é `_senha_hash`; nenhuma camada acima lê esse valor. Quem confere uma senha usa `Usuario.senha_confere` |
| **Hash fora de toda resposta** | `UsuarioOut` simplesmente não declara o campo — o schema de saída é a garantia, independentemente do que exista no modelo |
| **Senha fora dos logs** | O `__repr__` do `Usuario` não inclui o hash |
| **Autenticação por token** | JWT assinado com HS256, exigido em 5 dos 7 endpoints |
| **Autorização por dono** | Toda tarefa é verificada contra o usuário do token |
| **Sem enumeração de contas** | Nenhum endpoint recebe o id de outro usuário; o login responde a mesma mensagem para e-mail inexistente e senha errada |
| **Validação na borda** | O Pydantic recusa corpo malformado antes de qualquer lógica rodar |
| **CORS explícito** | Só as origens declaradas podem chamar a API pelo navegador |

### Sobre o bcrypt

O bcrypt gera um **salt aleatório** por senha: a mesma senha cadastrada por dois usuários
produz hashes diferentes, e o hash não permite recuperar a senha. Um hash tem 60
caracteres:

```
$2b$12$Kd8Yl0.zH3qF9x1mVN7uzuJq6Xw3sTgP2eR8kLmN4oPvB1cD5eF6G
 │  │  └── salt (22 caracteres) + hash (31 caracteres)
 │  └───── custo (12 = 2^12 iterações)
 └──────── identificador do algoritmo
```

**Verificação em aula:** cadastre dois usuários com a **mesma** senha e abra a tabela
`usuarios`. Os hashes serão diferentes. É a demonstração mais direta do que é um salt.

### Sobre o token de acesso

O token é um **JWT**: um texto que carrega quem é o usuário e até quando vale, assinado
com o segredo da aplicação. Validar não exige consulta ao banco — basta recalcular a
assinatura.

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiaWF0IjoxNzkz...uaz8ImlJZ77Dk
└──────── cabeçalho ────────────────┘ └──────── conteúdo ────────┘ └─ assinatura ─┘
```

**Verificação em aula:** cole um token em `jwt.io`, ou rode
`python -c "import base64,sys; print(base64.urlsafe_b64decode(sys.argv[1]+'=='))" <conteúdo>`.
O `sub`, o `iat` e o `exp` aparecem em texto claro.

É a demonstração do ponto que mais se confunde: **o conteúdo de um JWT não é secreto**.
Ele é apenas codificado em base64, não cifrado. A assinatura garante que ninguém
*alterou* o token, não que ninguém *leu*. Por isso só o id vai ali dentro — nome e e-mail
ficam fora.

Três regras sobre o segredo, verificadas na inicialização:

1. **É obrigatório.** Sem ele não há como emitir nem verificar sessão alguma.
2. **Mínimo de 32 bytes**, por causa da RFC 7518, seção 3.2: uma chave HMAC-SHA256 deve
   ter ao menos o tamanho da saída do hash, 256 bits. O PyJWT apenas avisa quando a chave
   é curta; aqui o aviso vira recusa, porque segredo fraco não dá sinal até ser explorado.
3. **O valor do `.env.example` é recusado com banco de servidor.** Ele está publicado no
   repositório, portanto não é segredo. Com SQLite funciona, porque ali é desenvolvimento.

### 401 e 403 são coisas diferentes

| Código | Significado | Quando |
|---|---|---|
| **401** | "Não sei quem você é" | Token ausente, mal formado, com assinatura inválida, expirado, ou de uma conta que não existe mais |
| **403** | "Sei quem você é, e isto não é seu" | Token válido pedindo a tarefa de outra conta |

A distinção tem efeito prático no cliente: 401 manda limpar a sessão e pedir login; 403
não — a sessão está boa, o pedido que não era.

O FastAPI responderia **403** para cabeçalho ausente, se deixado por conta própria. Por
isso o `HTTPBearer` é criado com `auto_error=False`: a ausência é detectada e vira
`NaoAutenticado`, que responde 401.

### Como a autorização é garantida

A verificação do dono não está em nenhuma rota. Está na assinatura de
`TarefaServico.buscar`:

```python
def buscar(self, tarefa_id: int, usuario_id: int) -> Tarefa:
```

O `usuario_id` é **obrigatório**. Enquanto era possível buscar uma tarefa sem dizer em
nome de quem, qualquer rota podia esquecer de verificar o dono — e foi exatamente o que
acontecia na versão 2.x. Agora esquecer não compila: não há de onde tirar a tarefa sem
informar o usuário.

`atualizar` e `remover` passam pelo mesmo `buscar`, e por isso herdam a verificação sem
repeti-la. A listagem não precisa de verificação nenhuma: o filtro já nasce com o
`usuario_id` do token, e não existe parâmetro para dizer outro.

A dependência `obter_usuario_autenticado` é declarada **no router** de tarefas, não em
cada função. Assim um endpoint novo nasce protegido: esquecer de pedir o usuário deixa a
rota sem acesso ao dono, e não aberta ao mundo. O padrão oposto — proteger rota por rota
— falha pelo esquecimento de uma só.

### A falha que esta versão fechou

Até a versão 2.2.0, **nenhum endpoint verificava a identidade de quem chamava**. Era
possível, sem credencial alguma:

| Chamada | O que devolvia |
|---|---|
| `GET /usuarios/{id}` | Nome, e-mail e data de cadastro de qualquer usuário |
| `GET /tasks?usuarioId=N` | As tarefas de qualquer usuário |
| `PATCH /tasks/{id}` | Alterava a tarefa de qualquer usuário |
| `DELETE /tasks/{id}` | Removia a tarefa de qualquer usuário |

Como os ids são inteiros sequenciais, bastava percorrer `1, 2, 3…`. É a categoria de
falha que o OWASP chama de *Broken Object Level Authorization*, e costuma ser a mais
comum em APIs reais.

Duas mudanças de desenho fecharam isso, e as duas são mais fortes do que acrescentar
`if`s de verificação:

- **`GET /usuarios/{id}` deixou de existir.** Foi substituído por `GET /usuarios/eu`, que
  não recebe id nenhum. Não há o que validar quando não há o que informar.
- **`usuarioId` saiu do corpo e da query.** O dono vem do token. Mandar `usuarioId` de
  outra pessoa em `POST /tasks` não faz nada: o campo não existe no schema e o Pydantic o
  descarta — há teste para isso.

O princípio é o mesmo nos dois casos: a forma mais confiável de impedir um pedido
indevido é não oferecer onde fazê-lo.

### O que **não** está implementado — e por quê

| Lacuna | Consequência | O que seria preciso |
|---|---|---|
| **Token não é revogável** | "Sair" é o cliente descartar o token; ele continua válido até expirar | Tabela de sessões, ou lista de revogados |
| **Sem *refresh token*** | A validade é longa (7 dias) para não obrigar a reentrar várias vezes ao dia; token vazado serve por esse tempo | Par de tokens: acesso curto e renovação longa |
| **Token no `localStorage` do cliente** | Legível por JavaScript da origem, o que inclui um ataque de XSS | Cookie `HttpOnly`, o que exige tratar CSRF |
| **Sem limite de tentativas de login** | Nada impede testar senhas em sequência | Contagem por IP ou conta, com espera progressiva |
| **Sem recuperação de senha** | Quem esquece a senha perde a conta | E-mail com token de uso único |
| **Sem HTTPS obrigatório** | Em produção, a senha e o token trafegariam em claro se alguém usar `http://` | Redirecionamento forçado na camada de hospedagem |

Nenhuma dessas lacunas reabre a falha fechada nesta versão: uma conta não alcança os
dados da outra. Todas são sobre o que acontece **depois** de um token ser emitido, ou
sobre o caminho até ele.

Registrar o que falta é parte da documentação técnica: um bom manual descreve tanto o que
o sistema faz quanto os limites dentro dos quais ele é seguro.

---

## 10. Decisões técnicas

### D-01 — FastAPI como framework

Gera documentação interativa automaticamente, valida dados por anotações de tipo
(reaproveitando o que já se sabe de tipagem Python) e tem sintaxe enxuta, o que mantém o
foco na regra de negócio e não na configuração do framework.

### D-02 — Arquitetura em camadas, com as regras nas entidades

A versão 1.0.0 tinha modelos sem comportamento — o que se chama de *modelo anêmico* — e
as regras de negócio dentro das funções de rota. O problema prático apareceu rápido: a
mesma RN-03 era implementada de uma forma na classe e de outra no endpoint.

A regra adotada: **se a informação pertence à entidade, o comportamento também**. Status e
data de conclusão são privados; `concluir` e `reabrir` são o único caminho. O custo é mais
camadas do que um CRUD de 7 endpoints estritamente precisa; o benefício é que invariante
virou invariante, e não convenção.

### D-03 — SQLite em desenvolvimento, PostgreSQL em produção

SQLite não exige instalação, o que permite clonar o projeto e rodar — e permite que a
suíte de testes rode em qualquer máquina. PostgreSQL é banco em servidor, adequado a
produção e ao que o Indicador 5 da UC exige.

A portabilidade não é gratuita: exigiu ligar a verificação de chave estrangeira no SQLite
([seção 3](#3-ambientes-e-banco-de-dados)) para que os dois ambientes se comportem igual.
Sem isso, a conveniência do SQLite viria acompanhada de uma classe de defeito que só
aparece em produção.

### D-04 — A tradução de nomes acontece na borda

O contrato da API é definido por quem a consome: aplicações front-end em JavaScript usam
camelCase. O Python usa snake_case.

A versão 1.0.0 resolvia nomeando os **atributos do modelo** em camelCase — ou seja,
deixando a convenção do cliente vazar para dentro do domínio. Agora o domínio fala Python
idiomático e os schemas fazem a conversão pelo `alias_generator`. `populate_by_name=True`
mantém a compatibilidade: a entrada aceita as duas formas.

### D-05 — `PATCH` com sentinela

A operação mais comum é alterar um campo só. Para distinguir "não mencionei o prazo" de
"quero apagar o prazo", há um objeto sentinela (`NAO_INFORMADO`): `None` não daria conta
das duas situações.

### D-06 — Enums em vez de texto solto

Os valores válidos de status e prioridade ficavam escritos em três lugares. Com enums, há
um único lugar de definição — e o peso de cada prioridade, usado na ordenação, vive junto
com ela.

Os campos de ordenação também são enum, o que corrigiu um defeito real: antes, um valor
inválido em `ordenarPor` caía silenciosamente na ordenação por data e o cliente nunca
sabia que o parâmetro havia sido ignorado. Agora devolve 422.

### D-07 — Exceções de domínio e um tratador único

Serviços e modelos nunca levantam `HTTPException`: levantam exceções próprias,
organizadas em hierarquia. `main.py` registra **um** tratador para `ErroDeDominio` e
atende a família inteira, porque o Starlette percorre a MRO da exceção.

Duas consequências: o domínio é reutilizável fora da web, e uma exceção nova já sai com o
código de status correto desde que herde da classe certa.

### D-08 — Interface para o hash de senha

`HashDeSenha` é classe abstrata e `HashBcrypt` a implementa. Não é cerimônia: o bcrypt
custa centenas de milissegundos por hash, de propósito. Com a interface no meio, a suíte
de testes injeta uma implementação instantânea e a aplicação segue usando o bcrypt.

### D-09 — `create_all()` em vez de Alembic

Ferramenta de migração é o padrão profissional para evoluir o esquema de um banco em
produção sem perder dados, e está fora do escopo da UC. `create_all()` cria o que falta e
**não altera** tabela existente: mudar o tipo de uma coluna exige apagar a tabela, o que
em desenvolvimento significa apagar o `todo_list.db`.

### D-10 — JWT para a sessão, e não token opaco com tabela

As duas formas de manter uma sessão autenticada:

| | JWT assinado | Token opaco + tabela `sessoes` |
|---|---|---|
| Validar | Recalcular a assinatura | Consultar o banco |
| Revogar | **Não dá** — vale até expirar | Apagar a linha |
| Custo | Nenhuma estrutura nova | Tabela + rotina de limpeza dos vencidos |

Foi escolhido o JWT. A revogação é a perda real, e ela se paga aqui porque não há
operação destrutiva irreversível nesta aplicação — a pior consequência de um token
vazado é alguém mexer nas tarefas de uma conta, não transferir dinheiro.

Uma ressalva honesta sobre a economia prometida: ela **não se realiza inteira** neste
projeto. `obter_usuario_autenticado` busca o usuário no banco a cada requisição, que é
exatamente a consulta que o token opaco exigiria. Isso é deliberado — ver a docstring da
função —, porque sem a consulta uma conta apagada continuaria funcionando até a
expiração, e nome e e-mail ficariam congelados no token. O que se ganha de fato é não
precisar de tabela de sessões nem de rotina de limpeza.

Sobre a biblioteca: é usado o **PyJWT**, não o `python-jose` que aparece em muitos
tutoriais. O PyJWT é o que a documentação do FastAPI passou a indicar, tem manutenção
ativa e faz só uma coisa. É o mesmo critério que levou a preferir o `bcrypt` direto ao
`passlib` ([D-08](#d-08--interface-para-o-hash-de-senha)).

---

### D-11 — O que não se pode pedir não precisa ser validado

Ao fechar a falha de autorização, havia duas formas de proceder:

1. Manter `usuarioId` no corpo e na query, e **validar** se corresponde ao token.
2. **Remover** os dois, e tirar o dono do token.

Foi escolhida a segunda. A primeira funciona, mas deixa no contrato um campo que não pode
discordar do token — informação duplicada que só serve para errar. E validação é código
que alguém precisa lembrar de escrever em cada rota nova.

O mesmo raciocínio aposentou o `GET /usuarios/{id}` em favor do `GET /usuarios/eu`: não
há id para validar quando não há id para informar.

É o princípio por trás das duas decisões: **a forma mais confiável de impedir um pedido
indevido é não oferecer onde fazê-lo.** Vale também para o `TarefaServico.buscar`, que
exige o `usuario_id` como parâmetro obrigatório — esquecer a verificação deixou de ser
uma possibilidade.

---

### D-12 — Datas sempre em UTC declarado

`datetime.now()` devolve o horário local da máquina **sem** dizer qual é esse fuso. O
Pydantic serializa esse valor como `2026-01-05T10:00:00`, e o JavaScript interpreta a
string como horário local **do navegador**. Com o servidor em UTC e o navegador em
Brasília, toda data chegaria três horas deslocada — e o deslocamento mudaria com o
horário de verão de quem está olhando.

A correção tem duas partes, porque o problema tem duas camadas:

1. `agora_utc()` substitui `datetime.now` nos `default` das colunas, gravando UTC com o
   fuso declarado.
2. O tipo `DataHoraUTC` reata o fuso na leitura. Isso é necessário porque
   `DateTime(timezone=True)` **não** resolve o caso: o PostgreSQL preserva o fuso, mas o
   SQLite o descarta e devolve o valor sem `tzinfo`. Sem o tipo próprio, o JSON de
   desenvolvimento e o de produção seriam diferentes.

É a mesma categoria de decisão do `PRAGMA foreign_keys=ON` ([seção
3](#3-ambientes-e-banco-de-dados)): eliminar uma divergência silenciosa entre os dois
bancos, em vez de deixá-la para ser descoberta depois do deploy.

> Bancos de desenvolvimento criados antes desta mudança têm datas gravadas em horário
> local, que passarão a ser lidas como UTC. Em desenvolvimento, apague o `todo_list.db`
> e deixe a aplicação recriá-lo.

### D-13 — O vocabulário do cliente é aceito na borda

A API aceita `status=todas` como "sem filtro" e `ordenarPor=recente` como apelido de
`criadoEm`. Nenhum dos dois é o nome canônico — são o vocabulário que o front-end já
usa: `todas` é o valor inicial dos seletores de filtro, e `recente` é como ele chama a
ordenação por data de criação.

A alternativa era recusar os dois com 422 e exigir que o cliente traduzisse antes de
cada chamada. Foi descartada por um motivo prático: a tradução é a mesma sempre, e
colocá-la em um lugar só — aqui — é mais confiável do que repeti-la em cada ponto de
chamada. É a mesma lógica da normalização de `postgres://` em `config.py`: aceitar o que
o mundo real manda, quando a intenção é inequívoca.

Isso **não** significa aceitar qualquer coisa. `status=inventado` continua devolvendo
422, e um apelido novo precisa ser declarado explicitamente. A diferença entre "aceitar
um sinônimo conhecido" e "ignorar o que não entendi em silêncio" é justamente o que o
enum de `CampoOrdenacao` foi criado para resolver ([D-06](#d-06--enums-em-vez-de-texto-solto)).

---

## 11. Testes

```bash
python -m pytest          # 188 passed
```

| Arquivo | Testes | O que verifica | Precisa de banco? |
|---|---|---|---|
| `test_dominio.py` | 37 | Regras de negócio direto nos objetos | Não |
| `test_configuracao.py` | 25 | Escolha do banco e normalização da URL | Não |
| `test_seguranca.py` | 12 | O contrato de hash e o `HashBcrypt` de verdade | Não |
| `test_banco.py` | 7 | Chave estrangeira e restrições de unicidade | SQLite em memória |
| `test_api.py` | 31 | Os 7 endpoints, códigos de status e contrato JSON | SQLite em memória |
| `test_autenticacao.py` | 34 | O token e o **isolamento entre contas** | SQLite em memória |
| `test_integracao_frontend.py` | 34 | O contrato com o front-end React | SQLite em memória |

A suíte roda **sem nenhum banco instalado**: usa SQLite em memória e substitui o bcrypt
por uma implementação instantânea, porque as duas coisas estão atrás de abstrações.

### Como a suíte é montada

`conftest.py` define `DATABASE_URL=sqlite://` **antes** de importar a aplicação — a
configuração fica em cache na primeira importação. Uma fixture recria as tabelas a cada
teste, e `obter_hasher` é substituído por `HashFake` via `dependency_overrides`.

`TestClient(app)` é usado **sem** `with` de propósito: assim o ciclo de vida não roda e
não tenta criar tabelas de novo — quem cuida disso é a fixture.

### Os cinco testes que mais importam

1. **Editar o título de uma tarefa concluída não altera `concluidoEm`** — a RN-03 de ponta
   a ponta, atravessando as quatro camadas.
2. **A resposta não contém `senha` nem `senhaHash`** — a RN-05 verificada no contrato.
3. **`?ordenarPor=inventado` devolve 422** — protege contra a volta do defeito silencioso.
4. **Tarefa com `usuario_id` inexistente é recusada pelo banco** — prova que o
   `PRAGMA foreign_keys` está ativo. Sem o ajuste, o SQLite aceitaria a linha órfã.
5. **Uma URL `postgres://` é normalizada** — prova que a credencial da hospedagem
   funciona colada como vem.

### Os testes que não podem falhar nunca

Os de isolamento, em `test_autenticacao.py`. Eles verificam que uma conta não lê, não
altera e não apaga a tarefa de outra — a falha que a versão 3.0.0 veio fechar.

Um deles merece destaque pela forma: `test_a_tarefa_recusada_continua_intacta` não se
contenta com o 403. Ele confere, depois, que a tarefa segue com o conteúdo original. A
razão é que um 403 devolvido **depois** de gravar a alteração seria pior do que não ter
verificação nenhuma — porque pareceria seguro.

### O arquivo que protege a integração

`test_integracao_frontend.py` verifica algo diferente dos outros: não se a API faz o que
promete, mas se ela fala **exatamente** o que o front-end já sabe consumir — nomes dos
campos, formato das datas, vocabulário dos filtros, forma do erro.

Esses testes são os únicos da suíte que falham por uma mudança que não é um defeito.
Renomear um campo de saída é uma decisão legítima; o que não pode é ser feita sem
perceber que a outra ponta depende dela. Cada teste ali aponta, no comentário, o arquivo
do front-end que o justifica.

### Os testes de domínio são os mais valiosos

Falham exatamente onde a regra está escrita, sem subir a aplicação, e rodam em
milissegundos. Eles só são possíveis porque as regras saíram das rotas e foram para as
entidades: na versão 1.0.0, testar a RN-03 exigia uma requisição HTTP.

### Bateria manual

A bateria de 20 casos executada pelo `/docs` continua válida como atividade de aula — é
ela que ensina a ler código de status e corpo de resposta. A suíte automatizada cobre os
mesmos casos e serve para outro propósito: impedir regressão.

---

## 12. Operação e implantação

Colocar a aplicação no ar não exige alterar código. Três passos:

### 1. Criar o banco PostgreSQL

Na plataforma escolhida, criar a instância e copiar a URL de conexão. A *database* precisa
existir; as **tabelas** a aplicação cria na subida.

### 2. Definir as variáveis de ambiente

| Variável | Valor |
|---|---|
| `DATABASE_URL` | A URL do banco. Pode ser colada como a plataforma entrega |
| `JWT_SECRET` | **Um valor gerado, nunca o do `.env.example`.** A aplicação recusa subir com o de exemplo quando o banco é de servidor |
| `ORIGENS_PERMITIDAS` | O domínio do front-end, separado por vírgula se houver mais de um |
| `JWT_EXPIRACAO_HORAS` | Opcional; o padrão é 168 (7 dias) |

Bancos gerenciados normalmente exigem SSL — o que se expressa como parâmetro na própria
URL (`?sslmode=require`).

Gere o segredo com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Trocar o `JWT_SECRET` invalida **todas** as sessões abertas: os tokens em circulação
foram assinados com o valor antigo e param de ser reconhecidos. Isso é indesejado em uma
troca de rotina, e é exatamente o que se quer em caso de suspeita de vazamento — é a
única forma de revogação disponível sem tabela de sessões.

### 3. Subir a aplicação

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Sem `--reload`: ele existe para desenvolvimento e reinicia o processo a cada alteração de
arquivo.

### Antes de considerar a implantação responsável

- **Autenticação por token**, pela falha descrita na [seção 9](#9-segurança).
- **Rotina de backup** do banco — item previsto nos conhecimentos da UC e hoje
  inexistente neste projeto.
- **Migrações versionadas**, para alterar esquema sem perder dados.

---

## 13. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | Comando executado de dentro de `app/` | Rodar a partir da raiz do projeto |
| `Can't load plugin: sqlalchemy.dialects:postgresql.psycopg` | Driver do PostgreSQL ausente | `pip install "psycopg[binary]"` |
| `Could not parse SQLAlchemy URL from string 'postgres://...'` | Versão sem a normalização de URL | Atualizar o projeto, ou usar `postgresql+psycopg://` |
| `connection to server ... failed` | Banco fora do ar, credencial errada ou SSL ausente | Conferir a `DATABASE_URL` e o `sslmode` |
| Alterei um modelo e a coluna não apareceu | `create_all` não altera tabela existente | Em desenvolvimento, apagar o `todo_list.db` e subir de novo |
| Tarefa órfã foi aceita no banco | `PRAGMA foreign_keys` não aplicado | Conferir o listener em `database.py`; rodar `tests/test_banco.py` |
| Erro ao instalar o bcrypt: versão não encontrada | `requirements.txt` com a linha `bcrypt<4.1`, de uma versão antiga do projeto | Remover o pin: o projeto usa a biblioteca `bcrypt` direto, sem `passlib`, e não fixa versão |
| `ValorInvalido` sobre uma senha que parecia curta | O limite do bcrypt é 72 **bytes**; caracteres acentuados contam mais de um byte cada | Senha mais curta, ou contar bytes e não caracteres ao validar na borda |
| `[Errno 10048] address already in use` | Porta 8000 ocupada | `uvicorn app.main:app --reload --port 8001` |
| Navegador bloqueia a requisição (CORS) | Origem não autorizada | Acrescentar a origem em `ORIGENS_PERMITIDAS` |
| `422` inesperado | Corpo fora do contrato | Ler o `detail` da resposta: ele indica campo e motivo |
| Avisos do Pydantic sobre `Field()` em campo de união | Interação entre FastAPI 0.115 e Pydantic 2.13 | Não é do projeto; reproduz-se com qualquer `response_model` com campo `X \| None` e some ao atualizar o FastAPI |
| O banco de desenvolvimento apareceu no `git status` | `*.db` fora do `.gitignore` | Acrescentar `*.db` e `git rm --cached todo_list.db` |

---

## 14. Próximos passos

Evoluções fora do escopo desta UC, registradas para quem for continuar o projeto, em
ordem de importância:

1. **Revogação de sessão e *refresh token*** — hoje o token vale até expirar e "sair" é
   o cliente descartá-lo. Um par de tokens (acesso curto + renovação longa) permitiria
   validade curta sem obrigar a reentrar, e uma lista de revogados permitiria encerrar
   uma sessão de verdade. Ver a [seção 9](#9-segurança).
2. **Rotina de backup e restore** do PostgreSQL, com periodicidade definida e restauração
   testada.
3. **Migrações com Alembic**, para evoluir o esquema sem apagar tabelas.
4. **Front-end** consumindo esta API, aproveitando o CORS já configurado.
5. **Paginação com metadados no corpo** — o total já vai no cabeçalho
   `X-Total-Count`, que resolve o essencial sem quebrar quem consome a resposta como
   array. Mudar o corpo para `{"total": 120, "itens": [...]}` só se justifica junto com
   uma mudança do cliente.
6. **Observabilidade** — log estruturado das requisições e de erros não previstos.

---

## 15. Rastreabilidade com os indicadores da UC

| Indicador (redação oficial do Plano de Curso) | Onde este projeto o evidencia |
|---|---|
| **1.** Configura o ambiente de desenvolvimento conforme as funcionalidades e características do aplicativo computacional para desktop. | Ambiente virtual, `requirements.txt`, configuração por variáveis de ambiente, repositório Git com `.gitignore` adequado ([seções 3](#3-ambientes-e-banco-de-dados) e [4](#4-instalação-e-execução)) |
| **2.** Desenvolve softwares de acordo com as melhores práticas da linguagem de programação selecionada. | Arquitetura em camadas, encapsulamento, injeção de dependência, docstrings, validação declarativa, hierarquia de exceções, suíte de testes ([seções 2](#2-arquitetura), [10](#10-decisões-técnicas) e [11](#11-testes)) |
| **3.** Elabora código conforme as funcionalidades e características do aplicativo computacional para desktops. | Os 7 endpoints e as regras RN-01 a RN-05 ([seções 7](#7-contrato-da-api) e [8](#8-regras-de-negócio)) |
| **4.** Realiza a compilação e depuração do código desenvolvido de acordo com orientações técnicas da IDE utilizada. | Depuração com breakpoints anexados ao `uvicorn`, leitura de traceback, `ECHO_SQL` para inspecionar o SQL gerado, bateria de testes e correção de defeitos ([seções 11](#11-testes) e [13](#13-solução-de-problemas)) |
| **5.** Utiliza comandos de integração dos objetos de bancos de dados com o código construído para desktop de acordo com premissas do sistema operacional (servidor) de rede. | Modelos ORM, chave estrangeira, consultas com filtro, ordenação e paginação, e integração com **PostgreSQL em servidor** ([seções 3](#3-ambientes-e-banco-de-dados) e [6](#6-modelo-de-dados)) |
| **6.** Elabora o manual de utilização do projeto de software desenvolvido conforme a orientação técnica. | Este manual, o `README.md` e a documentação viva gerada em `/docs` (OpenAPI) |

### Duas notas de alinhamento curricular

**Sobre a expressão "para desktop".** Os Indicadores 1, 3 e 5 usam essa expressão. Neste
projeto ela é interpretada como **aplicativo cliente-servidor desenvolvido e executado
localmente**: ambiente, IDE, código e servidor rodam integralmente na máquina do aluno,
ainda que o serviço seja consumido via HTTP. Reforça essa leitura o fato de que os
Conhecimentos oficiais da UC citam literalmente "API".

**Sobre o Indicador 5 e o banco de desenvolvimento.** O indicador exige integração com
banco "de acordo com premissas do sistema operacional (servidor) de rede". O **PostgreSQL
de produção atende**; o **SQLite de desenvolvimento não** — é arquivo local, não servidor
de rede.

Para que a evidência do Indicador 5 seja sólida, a turma precisa apontar o projeto para um
banco em servidor em algum momento da Fase 3, ainda que em contêiner local ou em serviço
gratuito. Rodar apenas em SQLite cobre os demais indicadores, mas deixa o 5 frágil.

---

**Documento de referência do projeto — UC 12, Fase 3 (Aulas 17 a 24).**
Ver o PTD completo em `ptd/PTD-UC12-Codificacao-Manutencao-Documentacao-Desktop.md`.

> **Atenção:** a Fase 3 do PTD ainda descreve a versão 1.0.0 — modelos sem comportamento,
> regras de negócio nas rotas e MySQL instalado na Aula 17. A sincronização do PTD com a
> arquitetura e o banco atuais está pendente.
