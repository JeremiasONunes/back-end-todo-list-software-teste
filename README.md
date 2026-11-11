# Todo List API

Backend de gerenciamento de tarefas construído com **FastAPI** e **SQLAlchemy**.

Projeto Integrador da **UC 12 — Codificação, Manutenção e Documentação de Aplicativos
para Desktop** — Curso Técnico em Informática, SENAC Minas Gerais.

**Versão:** 3.0.0 · **Stack:** Python 3.11+ · FastAPI · SQLAlchemy · Pydantic v2
**Banco:** SQLite em desenvolvimento · PostgreSQL em produção

---

> ## ⚠️ Leia antes de começar
>
> Esta é a **cópia de trabalho da UC 11**, e ela é diferente do projeto original em dois
> aspectos. Os dois são de propósito.
>
> **1. Não há testes automatizados, nem a ferramenta para rodá-los.** A pasta `tests/`, o
> arquivo `pytest.ini` e as dependências de teste foram removidos. Construir a suíte é o
> trabalho desta UC, e instalar o pytest é a primeira atividade da Aula 1.
>
> **Também não há repositório Git.** A primeira coisa a fazer, antes de escrever qualquer
> teste, é `git init` e commitar o projeto como ele chegou. A trilha é guiada por commits,
> e esse ponto de partida é o marco contra o qual todo o resto é comparado.
>
> **2. Este código contém defeitos introduzidos de propósito.** Não é um projeto de má
> qualidade: é um projeto que funciona, com erros plantados em pontos específicos para
> que você os encontre. Quantos são e onde estão, você não sabe — é isso que torna o
> diagnóstico real.
>
> O que isso significa na prática:
>
> - **Quando um teste que você escreveu falhar, a primeira hipótese é que ele achou um
>   defeito de verdade.** Confira o teste, mas não presuma que o erro é seu.
> - **Encontrar e corrigir o defeito é a atividade.** A sequência é sempre
>   `teste vermelho → diagnóstico → correção em app/ → teste verde`, e cada etapa é
>   avaliada.
> - **Você só altera `app/` com um teste vermelho que justifique.** Alterar a aplicação
>   para fazer um teste passar, sem ter diagnosticado um defeito, é o atalho que invalida
>   o trabalho. A pergunta de controle é: *"que teste prova que esta linha está errada?"*
> - **A documentação é a especificação.** Este README, o manual técnico e as docstrings
>   descrevem o que o sistema *deveria* fazer. Onde o código contradizer a documentação, é
>   o código que está errado.
>
> A seção [Segurança](#segurança) deste README merece atenção especial: ela descreve
> proteções que o projeto promete. Vale conferir, uma a uma, se o código as cumpre.

---

---

## O que a API faz

- Cadastra usuários com senha armazenada como hash bcrypt.
- Autentica por e-mail e senha, emitindo um **token JWT** de acesso.
- Cria, lista, atualiza e remove tarefas — sempre as **do próprio usuário**.
- Filtra, busca e ordena tarefas por status, prioridade, prazo e título.
- Controla automaticamente a data de conclusão de cada tarefa (RN-03).

A API **não possui interface gráfica**: expõe 7 endpoints HTTP que recebem e devolvem JSON.

Cinco dos sete exigem o token no cabeçalho `Authorization`. Os dois públicos são o
cadastro e o login — não há como pedir credencial de quem está criando a conta ou
tentando entrar nela.

---

## Começando em três comandos

Não é preciso instalar nem configurar banco de dados para rodar localmente:

```bash
python -m venv venv && venv\Scripts\Activate.ps1   # Windows (PowerShell)
pip install -r requirements.txt
Copy-Item .env.example .env                        # Windows (PowerShell)
uvicorn app.main:app --reload
```

Abra `http://localhost:8000/docs`. Na primeira execução, um arquivo `todo_list.db`
é criado na raiz do projeto com as tabelas prontas.

> O `.env` é necessário: `DATABASE_URL` e `JWT_SECRET` são obrigatórias e não têm valor
> padrão. O `.env.example` já vem com as duas preenchidas para desenvolvimento, então
> copiá-lo basta.

**Para experimentar pelo `/docs`:** cadastre-se em `POST /usuarios`, copie o
`accessToken` da resposta e cole-o no botão **Authorize** no topo da página. Sem isso,
os endpoints de `/tasks` respondem 401.

> O comando `uvicorn` roda a partir da **raiz do projeto** (a pasta
> `todo-list-backend/`), não de dentro de `app/`. Executado no lugar errado, o Python
> não encontra o pacote e responde `ModuleNotFoundError: No module named 'app'`.

---

## Banco de dados

A aplicação usa um banco diferente em cada ambiente, e a escolha é feita por **uma
única variável de ambiente**:

| Ambiente | Banco | Como é fornecido |
|---|---|---|
| Desenvolvimento | SQLite em arquivo (`todo_list.db`) | `DATABASE_URL` no arquivo `.env` |
| Produção | PostgreSQL | `DATABASE_URL` no ambiente de execução |
| Testes | SQLite em memória | `DATABASE_URL` definida pela própria suíte |

A variável é **obrigatória** e não tem valor padrão. Sem ela a aplicação recusa subir, com
uma mensagem que diz onde o `.env` foi procurado e se foi encontrado. A alternativa — cair
em SQLite quando a variável falta — esconde um problema: quando o padrão coincide com o
valor esperado, não há como saber se o `.env` foi lido ou se a aplicação apenas caiu no
padrão.

Nenhum modelo, repositório, serviço ou rota muda ao trocar de banco. Quem conhece o
banco em uso é apenas o módulo `app/database.py`.

### Apontar para o PostgreSQL

Basta definir a variável — em um `.env` local ou no painel da plataforma de hospedagem:

```env
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/banco?sslmode=require
```

Duas comodidades já tratadas no código, para não virar problema no dia do deploy:

- **Esquema legado.** Várias plataformas entregam a URL começando com `postgres://`,
  que o SQLAlchemy 2 não aceita mais. A aplicação corrige o esquema e resolve o driver
  automaticamente — a URL pode ser colada como vem. Quem escreveu o driver
  explicitamente (`postgresql+psycopg2://`, por exemplo) é respeitado.
- **Conexão derrubada por inatividade.** Em banco gerenciado é o erro mais comum. A
  aplicação liga `pool_pre_ping` e renova conexões a cada 30 minutos quando o banco é
  um servidor; em SQLite, nada disso se aplica e não é configurado.

O PostgreSQL precisa que a *database* exista previamente — normalmente a própria
plataforma a cria. As **tabelas** a aplicação cria sozinha ao subir.

### Chave estrangeira no SQLite

O SQLite vem com a verificação de chave estrangeira **desligada** por padrão. A
aplicação deve ligá-la em cada conexão.

Sem esse ajuste, o banco local aceitaria uma tarefa apontando para um usuário
inexistente e o PostgreSQL recusaria a mesma operação em produção — divergência
silenciosa entre ambientes é a categoria de defeito mais caro de encontrar.

### Quando o projeto crescer

`create_all()` cria as tabelas que faltam, mas **não altera** tabela existente. Mudar
o tipo de uma coluna em um banco que já tem dados é trabalho de ferramenta de
migração, como o **Alembic** — ainda não usado aqui.

---

## Configuração

`DATABASE_URL` e `JWT_SECRET` são **obrigatórias**; as demais são opcionais. Veja o
[`.env.example`](.env.example) para a lista completa e comentada — ele já vem com as duas
ativas, de modo que copiá-lo para `.env` resulta em um projeto que roda.

| Variável | Para quê | Padrão |
|---|---|---|
| `DATABASE_URL` | Banco de dados a usar | **nenhum** — ausente, a aplicação recusa subir |
| `JWT_SECRET` | Chave que assina os tokens de acesso | **nenhum** — ausente, a aplicação recusa subir |
| `JWT_EXPIRACAO_HORAS` | Validade do token | `168` (7 dias) |
| `ORIGENS_PERMITIDAS` | Origens liberadas no CORS, separadas por vírgula | `http://localhost:5173` e `127.0.0.1:5173` |
| `ECHO_SQL` | Imprime no terminal todo SQL gerado pelo ORM | desligado |

Sobre o `JWT_SECRET`, três regras que a aplicação verifica na inicialização:

- **É obrigatório.** Sem ele não há como emitir nem verificar sessão alguma.
- **Precisa de pelo menos 32 bytes** (RFC 7518, seção 3.2: uma chave HMAC-SHA256 deve ter
  256 bits). O PyJWT apenas avisa quando a chave é curta; aqui o aviso vira recusa.
- **O valor do `.env.example` é recusado com banco de servidor.** Ele está publicado no
  repositório, portanto não é segredo: quem o conhece assina um token para qualquer
  usuário. Com SQLite ele funciona, porque ali é desenvolvimento.

Gere o seu com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> O `.env` **nunca** é versionado — ele já consta no `.gitignore`, junto com o arquivo
> `*.db` do banco de desenvolvimento.

---

## Pré-requisitos

| Item | Versão | Para quê |
|---|---|---|
| Python | 3.11 ou superior | Executar a aplicação e os testes |
| Git | qualquer | Versionamento |
| PostgreSQL | 14 ou superior | **Somente em produção** — ou para testar o banco de produção localmente |

Para desenvolver e rodar a suíte de testes, Python é o único requisito: o SQLite vem
na biblioteca padrão.

---

## Endpoints

| # | Método | Caminho | Descrição | Token | Sucesso |
|---|---|---|---|---|---|
| 1 | POST | `/usuarios` | Cadastra um usuário e abre a sessão | — | 201 |
| 2 | POST | `/usuarios/login` | Autentica e devolve o token | — | 200 |
| 3 | GET | `/usuarios/eu` | Dados da própria conta | **sim** | 200 |
| 4 | POST | `/tasks` | Cria uma tarefa para si | **sim** | 201 |
| 5 | GET | `/tasks` | Lista as próprias tarefas, com filtros | **sim** | 200 |
| 6 | PATCH | `/tasks/{tarefa_id}` | Atualiza uma tarefa sua | **sim** | 200 |
| 7 | DELETE | `/tasks/{tarefa_id}` | Remove uma tarefa sua | **sim** | 204 |

Os campos do JSON são em **camelCase** (`usuarioId`, `criadoEm`, `concluidoEm`). Do
lado do Python os nomes são `snake_case`, e a tradução acontece nos schemas, na borda
da aplicação. A entrada aceita as duas formas.

### Exemplos

**Cadastrar usuário** — `POST /usuarios`

```json
{ "nome": "Ana Souza", "email": "ana@exemplo.com", "senha": "senha123" }
```

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwi...",
  "tokenType": "bearer",
  "usuario": {
    "id": 1,
    "nome": "Ana Souza",
    "email": "ana@exemplo.com",
    "criadoEm": "2026-10-05T14:32:35.833782Z"
  }
}
```

O cadastro já devolve a sessão aberta: quem acabou de criar a conta está autenticado por
definição, e exigir um login em seguida seria pedir a mesma senha duas vezes.

A senha não aparece na resposta: o schema de saída simplesmente não a declara.
Repetir o cadastro devolve `409` com `{"detail": "E-mail já cadastrado."}`.

**Usar o token** — em toda chamada protegida:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Sem o cabeçalho, a resposta é `401` com
`{"detail": "É necessário autenticar-se para acessar este recurso."}`.

**Criar tarefa** — `POST /tasks`

```json
{ "titulo": "Entregar o relatório", "prioridade": "alta", "prazo": "2026-12-20" }
```

Não há `usuarioId` no corpo: o dono é sempre o usuário do token. O campo saiu do contrato
justamente para que não exista como pedir que a tarefa seja de outra pessoa.

```json
{
  "id": 1,
  "usuarioId": 1,
  "titulo": "Entregar o relatório",
  "status": "pendente",
  "prioridade": "alta",
  "prazo": "2026-12-20",
  "criadoEm": "2026-10-05T14:32:35.842926Z",
  "atualizadoEm": "2026-10-05T14:32:35.842927Z",
  "concluidoEm": null
}
```

Toda tarefa nasce `pendente` — o status não é aceito na criação (RN-02).

**Concluir tarefa** — `PATCH /tasks/1` com `{ "status": "concluida" }` preenche
`concluidoEm`. Voltar para `pendente` limpa o campo. Editar apenas o título de uma
tarefa já concluída **preserva** a data original (RN-03).

**Listar com filtros** — `GET /tasks?status=pendente&ordenarPor=prioridade`
devolve as pendentes **do usuário do token**, da mais urgente para a menos. Um valor inválido em `ordenarPor`
devolve `422`, e não uma ordenação trocada em silêncio.

| Parâmetro | Valores | Padrão |
|---|---|---|
| `status` | `pendente`, `concluida` ou `todas` (sem filtro) | sem filtro |
| `prioridade` | `baixa`, `media`, `alta`, `urgente` ou `todas` | sem filtro |
| `prazoAte` | data `AAAA-MM-DD` | sem filtro |
| `busca` | texto; filtra pelo título, ignorando maiúsculas | sem filtro |
| `ordenarPor` | `criadoEm` (ou `recente`), `prazo`, `prioridade` | `criadoEm` |
| `ordem` | `asc`, `desc` | o sentido natural do campo |
| `limit` | 1 a 200 | 50 |
| `offset` | 0 ou mais | 0 |

Três comportamentos que valem registro:

- **Omitir `ordem` não significa decrescente**, significa "use o sentido natural do
  campo": as mais recentes primeiro em `criadoEm`, o prazo mais próximo primeiro em
  `prazo`, a urgente primeiro em `prioridade`. Um padrão único para os três acertaria
  em um e erraria em dois.
- **Tarefa sem prazo vai para o fim** nos dois sentidos. Sem isso o resultado
  dependeria do banco: o SQLite trata `NULL` como o menor valor de todos e o
  PostgreSQL o posiciona de forma diferente em cada sentido.
- **O total vem no cabeçalho `X-Total-Count`**, contando quantas tarefas atendem ao
  filtro independentemente de `limit` e `offset`. O corpo continua sendo um array
  puro — trocá-lo por `{"total": …, "itens": […]}` quebraria quem já o consome.

---

## Estrutura do projeto

```
todo-list-backend/
├── app/
│   ├── __init__.py
│   ├── main.py               # aplicação, CORS, rotas e tradução de erros em HTTP
│   ├── config.py             # Configuracao imutável; escolha do banco por URL
│   ├── database.py           # engine, sessão, Base e os ajustes por dialeto
│   ├── enums.py              # StatusTarefa, PrioridadeTarefa, CampoOrdenacao, Ordem
│   ├── exceptions.py         # hierarquia de exceções de domínio
│   ├── models.py             # Usuario e Tarefa — dados + comportamento
│   ├── schemas.py            # contrato JSON e tradução snake_case ↔ camelCase
│   ├── security.py           # HashDeSenha (interface) e HashBcrypt
│   ├── tempo.py              # UTC: agora_utc() e a coluna DataHoraUTC
│   ├── tokens.py             # emissão e leitura do token JWT
│   ├── validacao.py          # mensagens de validação do Pydantic em pt-BR
│   ├── repositories.py       # RepositorioBase (ABC) + repositórios concretos
│   ├── services.py           # UsuarioServico e TarefaServico
│   ├── dependencies.py       # montagem dos objetos injetados nas rotas
│   └── routers/
│       ├── __init__.py
│       ├── usuarios.py       # POST /usuarios, POST /usuarios/login, GET /usuarios/eu
│       └── tasks.py          # CRUD de /tasks
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # SQLite em memória e hash instantâneo
│   ├── test_dominio.py       # regras de negócio, sem banco e sem HTTP
│   ├── test_banco.py         # chaves estrangeiras e restrições do banco
│   ├── test_configuracao.py  # escolha do banco e normalização da URL
│   ├── test_api.py           # endpoints e contrato JSON
│   ├── test_autenticacao.py  # token, 401/403 e isolamento entre contas
│   └── test_integracao_frontend.py  # o contrato com o front-end React
├── docs/
│   ├── manual_tecnico.md     # documentação técnica completa
│   └── roteiro-de-construcao-7-dias.md
├── cliente_teste.py          # script da Aula 21 (consome a API, aplica algoritmos)
├── pytest.ini
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Arquitetura

O projeto é organizado em camadas, com uma regra clara de dependência: **cada camada
só conhece a de baixo**.

```
   routers/          HTTP: recebe requisição, devolve resposta
       ↓             (não sabe SQL, não decide regra de negócio)
   services.py       Regras de negócio e orquestração
       ↓             (não sabe HTTP, não escreve SQL)
   repositories.py   Acesso ao banco
       ↓             (não decide regra de negócio)
   models.py         Entidades com seus dados e seus invariantes
```

Três consequências práticas:

- **As regras de negócio moram nas entidades.** A RN-03 (data de conclusão) não está
  em nenhuma rota: está nos métodos `concluir` e `reabrir` da `Tarefa`, que são o
  único caminho para mudar o status. Não existe forma de deixar uma tarefa em estado
  inconsistente a partir de fora.
- **O domínio não conhece HTTP.** Serviços e modelos levantam exceções próprias
  (`app/exceptions.py`); é `main.py` que as traduz em código de status, com um único
  tratador para toda a hierarquia. Os mesmos serviços funcionariam em um programa de
  terminal.
- **Trocar de banco não toca no código.** SQLite e PostgreSQL diferem em uma variável
  de ambiente e em algumas opções de conexão, concentradas em `app/database.py`.

---

## Testes

Este projeto **não tem testes automatizados** — e é isso que você vai construir.

A suíte é o produto da UC 11: seis blocos de trabalho em que ela é escrita do zero, um
arquivo por vez, até cobrir as regras de negócio, o banco, a configuração, a segurança, os
endpoints e a autenticação. A ferramenta (`pytest`) também não está instalada: instalá-la
é a primeira atividade.

Por enquanto, a verificação disponível é manual, pela documentação interativa em `/docs`.

---

## Script cliente

O `cliente_teste.py` consome a API de fora, como um cliente real faria, e aplica sobre
a resposta os algoritmos de ordenação, busca e recursividade da Aula 21.

```bash
uvicorn app.main:app --reload      # em um terminal
python cliente_teste.py            # em outro
```

Ele espera um usuário de `id = 1` com algumas tarefas cadastradas — crie-as pelo
`/docs` antes de rodar, ou ajuste a constante `USUARIO_ID` no topo do arquivo.

---

## Erros comuns

| Mensagem | Causa provável | Solução |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | Comando executado de dentro de `app/` | Rodar a partir da raiz do projeto |
| `Can't load plugin: sqlalchemy.dialects:postgresql.psycopg` | Driver do PostgreSQL ausente | `pip install "psycopg[binary]"` |
| `Could not parse SQLAlchemy URL from string 'postgres://...'` | URL legada em versão sem a normalização | Atualizar o projeto, ou usar `postgresql+psycopg://` |
| `connection to server ... failed` | Banco de produção fora do ar ou credencial errada | Conferir a `DATABASE_URL` e o `sslmode` |
| `[Errno 10048] address already in use` | Porta 8000 ocupada | `uvicorn app.main:app --reload --port 8001` |
| Navegador bloqueia a requisição (CORS) | Origem não autorizada | Acrescentar a origem em `ORIGENS_PERMITIDAS` |
| Alterei um modelo e a coluna não apareceu | `create_all` não altera tabela existente | Em desenvolvimento, apagar o `todo_list.db` e subir de novo |
| Avisos do Pydantic sobre `Field()` em campo de união | Interação entre FastAPI 0.115 e Pydantic 2.13 | Não é do projeto; some ao atualizar o FastAPI |

---

## Integração com o front-end

Esta API é o backend do front-end React em `todo-list-main/`. O contrato entre os dois
não está escrito no código de nenhum dos lados — ele vive no formato do JSON e no
vocabulário dos parâmetros. É por isso que ele precisa ser verificado como teste:
renomear `criadoEm` ou mudar um valor de enum não quebraria nada do lado do servidor, e
a integração falharia apenas na hora de ligar as duas pontas.

### O que o backend faz para encaixar

| Ponto | Decisão |
|---|---|
| **Nomes dos campos** | JSON em camelCase (`usuarioId`, `criadoEm`, `concluidoEm`), igual aos `@typedef` de `taskService.js`. O domínio continua em `snake_case`; a tradução é feita pelo `alias_generator` dos schemas |
| **Datas** | Sempre em UTC com fuso declarado (`2026-01-05T10:00:00Z`). Sem o `Z`, o `new Date()` do JavaScript leria a string como horário local do navegador |
| **`prazo`** | Só a data (`AAAA-MM-DD`), sem hora e sem fuso — é o que o `formatarPrazo` do front espera para tratá-lo como meia-noite local |
| **Filtro em `todas`** | Os seletores do front começam nesse valor e o enviam na requisição. A API o entende como "sem filtro" em vez de recusar com 422 |
| **`ordenarPor=recente`** | Aceito como apelido de `criadoEm`: é o nome que o `useTasks.js` usa para o mesmo critério |
| **Sentido da ordenação** | Omitir `ordem` usa o sentido natural de cada campo, que é o que a função `ordenar()` do front já fazia no cliente |
| **Total de registros** | No cabeçalho `X-Total-Count`, liberado ao navegador via `expose_headers`. O corpo segue sendo um array, que é como o front o consome |
| **Erros** | `detail` é **sempre** uma frase, em português, inclusive nos 422 de validação. Os formulários do front exibem essa mensagem direto na tela com `setErro(e.message)` |
| **CORS** | Libera `http://localhost:5173` e `http://127.0.0.1:5173` (portas padrão do Vite) e expõe o cabeçalho `Authorization` no *preflight* |
| **Sessão** | O cadastro e o login devolvem `{accessToken, tokenType, usuario}` — o usuário vem junto para que entrar seja uma chamada só |

### Estado da integração: pendente

**O front-end ainda não consome esta API.** Ele continua mockado no `localStorage`, e a
migração é a "Fase 9" do roteiro dele — ainda não executada. Os dois lados estão
deliberadamente fora de sincronia neste momento.

O que isso significa na prática: se o front-end de hoje fosse apontado para esta API sem
alteração, **todas as telas de tarefas responderiam 401**, porque ele não envia o
cabeçalho `Authorization` em chamada alguma.

### O que a integração vai exigir do front-end

Nenhum destes itens é do backend; estão listados aqui porque é esta API que os determina.

| # | Mudança | Por quê |
|---|---|---|
| 1 | Criar `services/httpClient.js` com a URL base em `VITE_API_URL` | Substitui o `mockStorage.js` como único ponto de contato com "onde o dado mora" |
| 2 | Guardar o **token** em `authStorage.js`, não o id do usuário | A API identifica quem chama pelo token; o id perde a função |
| 3 | Anexar `Authorization: Bearer <token>` em toda chamada protegida | 5 dos 7 endpoints o exigem |
| 4 | Rehidratar a sessão por `GET /usuarios/eu` | O antigo `GET /usuarios/{id}` não existe mais |
| 5 | Tirar `usuarioId` do `POST /tasks` e do `GET /tasks` | Saiu do contrato; o dono vem do token |
| 6 | Traduzir o **401** do login no `null` que o `AuthContext` espera | Credencial errada é fluxo normal no front e exceção aqui — único ponto do contrato que não é tradução direta |
| 7 | Encerrar a sessão quando a API responder 401 | Token expirado no meio do uso deve levar ao login, não deixar a tela em erro permanente |
| 8 | Delegar busca, filtros e ordenação à API | Com o `limit` padrão de 50, filtrar no cliente só alcançaria a primeira página |
| 9 | Ler `X-Total-Count` para os números do painel | O painel conta sobre a lista recebida, que pode estar truncada |

Os itens 1, 8 e 9 já eram necessários antes da autenticação; de 2 a 7 vieram com ela.

Quando a integração acontecer, os dois sobem juntos:

```bash
uvicorn app.main:app --reload     # backend em :8000
npm run dev                       # front-end em :5173, na pasta todo-list-main/
```

---

## Segurança

### O que está implementado

| Proteção | Como |
|---|---|
| **Senha nunca em texto puro** | `bcrypt` com custo 12 e salt aleatório por senha (RN-05). O hash é privado no modelo e não é declarado em nenhum schema de saída |
| **Senha nunca em log** | O `__repr__` do `Usuario` não inclui o hash |
| **Autenticação por token** | JWT assinado com HS256; segredo obrigatório, de no mínimo 32 bytes, recusado em produção se for o do `.env.example` |
| **Autorização por dono** | Toda tarefa é verificada contra o usuário do token. `TarefaServico.buscar` exige o `usuario_id` como parâmetro obrigatório — esquecer a verificação deixa de ser possível |
| **Sem enumeração de contas** | Não há endpoint que receba o id de outro usuário. O login responde a mesma mensagem para e-mail inexistente e senha errada |
| **Validação na borda** | O Pydantic recusa corpo malformado antes de qualquer lógica rodar |
| **CORS explícito** | Só as origens declaradas podem chamar a API pelo navegador |

Os códigos 401 e 403 são distintos de propósito: **401** é "não sei quem você é" (token
ausente, inválido ou expirado) e **403** é "sei quem você é e esta tarefa não é sua".

### O que **não** está implementado — e por quê

| Lacuna | Consequência | O que seria preciso |
|---|---|---|
| **Token não é revogável** | "Sair" é o cliente descartar o token; ele continua válido até expirar | Tabela de sessões, ou lista de tokens revogados |
| **Sem *refresh token*** | A validade é longa (7 dias) para não obrigar a entrar de novo várias vezes ao dia. Token vazado serve por esse tempo | Par de tokens: um curto de acesso e um longo de renovação |
| **Token no `localStorage`** | Legível por JavaScript que rode na origem — o que inclui um ataque de XSS | Cookie `HttpOnly`, o que exige tratar CSRF |
| **Sem limite de tentativas de login** | Nada impede testar senhas em sequência | Contagem por IP ou por conta, com espera progressiva |
| **Sem recuperação de senha** | Quem esquece a senha perde a conta | Envio de e-mail com token de uso único |

Nenhuma dessas lacunas reabre a falha que a autenticação veio fechar: uma conta não
alcança os dados da outra. Elas são sobre o que acontece **depois** de um token ser
emitido ou vazar.

---

## Limitações conhecidas

- **Sem migrações.** `create_all()` cria o que falta, mas não altera tabela existente.
  Mudar uma coluna em banco com dados é trabalho do Alembic, ainda não usado aqui.
- **Sem log estruturado.** Erros de domínio viram JSON sem registro; erros não previstos
  contam com o log do `uvicorn`.
- **Cadastro concorrente de e-mail.** A verificação de duplicata e a inserção não são
  atômicas: duas requisições simultâneas com o mesmo e-mail podem resultar em `500` em
  vez de `409`. A restrição `UNIQUE` do banco garante a integridade; falta converter o
  `IntegrityError` na exceção de domínio.
- **Paginação sem metadados no corpo.** O total vai no cabeçalho `X-Total-Count`; o corpo
  é um array puro, por compatibilidade com o cliente atual.

---

## Documentação

- **Manual técnico:** [`docs/manual_tecnico.md`](docs/manual_tecnico.md) — arquitetura,
  modelo de dados, contrato da API, regras de negócio, decisões técnicas, implantação e
  rastreabilidade com os indicadores da UC
- **Roteiro de construção:** [`docs/roteiro-de-construcao-7-dias.md`](docs/roteiro-de-construcao-7-dias.md)
  — como construir o projeto do zero em sete blocos de trabalho
- **Documentação viva (OpenAPI):** `/docs` e `/redoc` com a aplicação em execução
- **PTD da UC 12:** `ptd/PTD-UC12-Codificacao-Manutencao-Documentacao-Desktop.md`
