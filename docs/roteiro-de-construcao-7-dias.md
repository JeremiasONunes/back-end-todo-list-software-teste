# Roteiro de Construção em 7 Dias — Todo List API

Roteiro para construir o backend **do zero até a versão 2.1.0**: API FastAPI em camadas,
regras de negócio dentro das entidades, SQLite em desenvolvimento, PostgreSQL preparado
para produção e 109 testes automatizados.

> A versão **2.2.0** do repositório acrescenta a camada de alinhamento com o front-end
> React — os módulos `app/tempo.py` e `app/validacao.py` e os 29 testes de
> `tests/test_integracao_frontend.py`, totalizando 138. Isso fica **fora** destes sete
> dias: é trabalho de integração, não de construção do backend. Ver a seção "Integração
> com o front-end" do README.

Cada etapa deste roteiro existe também como **projeto completo e executável** em
[`../../todo-list-passo-a-passo/`](../../todo-list-passo-a-passo/) — uma pasta `dia-NN/`
por dia, com o seu próprio README e a sua lista de commits. Serve para conferir a própria
solução ou para entrar no meio do caminho, e a comparação entre duas etapas mostra
exatamente o que mudou de um dia para o outro.

---

## Premissas

| Item | Valor |
|---|---|
| Ritmo previsto | 3 a 4 horas por dia — cerca de **21 a 28 horas** no total |
| Produto final | 13 módulos em `app/` (~1.440 linhas) e 5 arquivos de teste (109 testes) |
| Pré-requisitos | **Apenas Python 3.11+**, Git e VS Code |
| Conhecimento prévio | Python com orientação a objetos: classes, herança, propriedades e exceções |

Note o que **não** é pré-requisito: nenhum servidor de banco de dados. O projeto roda em
SQLite, que vem na biblioteca padrão do Python, e o PostgreSQL só entra quando houver
produção de verdade. Isso significa que qualquer máquina do laboratório consegue
acompanhar o roteiro inteiro sem instalação prévia.

Os tempos são estimativa de esforço, não de calendário. Se um dia render menos, o
importante é **não avançar de camada sem a anterior verificada** — é isso que impede a
dívida de se acumular até o último dia.

---

## A regra de ouro: construir de dentro para fora

A ordem dos dias não é arbitrária. Ela segue a direção das dependências da arquitetura:
cada camada só conhece a de baixo, então cada camada só pode ser construída depois dela.

```
Dia 6   routers/ + schemas      HTTP
Dia 5   services.py             regras de aplicação
Dia 4   repositories.py         persistência
Dia 3   models.py (Tarefa)      domínio
Dia 2   models.py (Usuario)     domínio
Dia 1   config + database       infraestrutura
```

Construir na ordem inversa — começar pelas rotas, como é tentador — obriga a colocar
regra de negócio dentro do endpoint "só por enquanto". Esse "por enquanto" é exatamente o
que produziu a versão 1.0.0, com modelos sem comportamento e regras espalhadas.

---

## Visão geral

| Dia | Foco | Entrega verificável |
|---|---|---|
| 1 | Ambiente, configuração e conexão | API no ar respondendo em `/`, banco SQLite criado |
| 2 | Vocabulário do domínio e entidade `Usuario` | Tabela `usuarios` criada, senha gravada como hash |
| 3 | Entidade `Tarefa` e a RN-03 | 22 testes de domínio verdes, sem banco |
| 4 | Repositórios | Consulta com filtro e ordenação funcionando |
| 5 | Serviços | Fluxo completo do sistema exercitável sem HTTP |
| 6 | Borda HTTP | 7 endpoints no `/docs`, contrato em camelCase |
| 7 | Testes e documentação | 109 testes verdes, README e manual |

---

## Dia 1 — Esqueleto que roda

**Objetivo:** ter uma aplicação que sobe, conecta ao banco e responde a uma requisição.
Nada de domínio ainda.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `.gitignore` | `.env`, `venv/`, `__pycache__/`, `*.pyc`, `.vscode/`, **`.pytest_cache/`** e **`*.db`** |
| `requirements.txt` | fastapi, uvicorn[standard], sqlalchemy, pydantic[email], python-dotenv, bcrypt, psycopg[binary], requests, pytest, httpx |
| `.env.example` | `DATABASE_URL` ativa (obrigatória) e as demais variáveis comentadas |
| `app/config.py` | `CAMINHO_DO_ENV` / `ENV_ENCONTRADO`, `Configuracao` (dataclass congelada), `normalizar_url()`, `do_ambiente()`, as propriedades `dialeto` / `banco_em_memoria` / `banco_em_servidor`, e `obter_configuracao()` com cache |
| `app/database.py` | `_opcoes_do_engine()`, o listener do `PRAGMA foreign_keys`, `engine`, `SessionLocal`, `Base`, `criar_tabelas()`, `obter_sessao()` |
| `app/main.py` | `FastAPI(...)`, `lifespan` chamando `criar_tabelas()`, rota `GET /` |

**A decisão de projeto do dia: um banco por ambiente, uma variável só.**

| Ambiente | Banco | Como é fornecido |
|---|---|---|
| Desenvolvimento | SQLite em arquivo | `DATABASE_URL` no arquivo `.env` |
| Produção | PostgreSQL | `DATABASE_URL` no ambiente de execução |
| Testes | SQLite em memória | `DATABASE_URL` definida pela própria suíte |

A variável é **obrigatória** e não tem valor padrão: sem ela, a aplicação recusa subir.

Três detalhes que custam pouco agora e evitam problema depois:

1. **`normalizar_url()`** — plataformas de hospedagem entregam a URL do PostgreSQL
   começando com `postgres://`, que o SQLAlchemy 2 não aceita mais. Corrigir no código
   significa que a URL pode ser colada como vem, no dia do deploy.
2. **Opções por dialeto** — SQLite em memória precisa de `StaticPool` (senão cada
   operação encontra um banco vazio); banco em servidor precisa de `pool_pre_ping` e
   `pool_recycle` (senão a conexão cai por inatividade).
3. **`PRAGMA foreign_keys=ON`** — o SQLite vem com a verificação de chave estrangeira
   **desligada**. Sem ligar, o banco de desenvolvimento aceitaria dados que o PostgreSQL
   recusaria em produção. O efeito disso só fica visível no Dia 3, quando a `Tarefa`
   ganhar a chave estrangeira, e é testado no Dia 7.

**Ordem de trabalho:** ambiente virtual e dependências → repositório Git com `.gitignore`
**antes** do primeiro commit → `config.py` → `database.py` → `main.py`.

**Como verificar**

A verificação deste dia é **manual**: a pasta `tests/` só nasce no Dia 2, junto da primeira
entidade. Rodar `python -m pytest` aqui responde `no tests ran`.

```bash
cp .env.example .env              # obrigatório: DATABASE_URL não tem padrão
uvicorn app.main:app --reload     # da raiz do projeto, não de dentro de app/
```

- `GET http://localhost:8000/` devolve 200.
- `http://localhost:8000/docs` abre a Swagger UI.
- O arquivo `todo_list.db` aparece na raiz do projeto.
- `git status` **não** lista nem o `.env` nem o `todo_list.db`.

**Armadilhas do dia**

- Rodar o `uvicorn` de dentro de `app/` → `ModuleNotFoundError: No module named 'app'`.
- Chamar `load_dotenv()` sem argumento, que é como quase todo tutorial escreve. A busca
  parte do diretório de trabalho, então rodar o mesmo comando de outra pasta faz o `.env`
  ser **ignorado em silêncio** e a aplicação cair no banco padrão sem avisar. Aponte o
  caminho: `load_dotenv(Path(__file__).resolve().parent.parent / ".env")`.
- Esperar que o `.env.example` copiado já configure algo: ele é 100% comentário, de
  propósito, porque todas as variáveis são opcionais. É preciso **descomentar** a linha.
- Esquecer `*.db` no `.gitignore` — o banco de desenvolvimento de cada pessoa vai para o
  repositório e gera conflito em todo `pull`.
- Criar o `.gitignore` depois do primeiro commit: o `.env` já entrou no histórico.
- Chamar `create_all()` na importação do módulo, e não no `lifespan`: importar a
  aplicação passa a exigir um banco acessível, o que atrapalha qualquer teste depois.
- Montar a URL do banco a partir de cinco variáveis separadas (host, porta, usuário,
  senha, nome). Funciona, mas não é como as plataformas entregam a credencial — e
  obriga a reescrever a configuração no dia do deploy.

**Commit:** `Configura projeto FastAPI, conexão com o banco e rota de status`

---

## Dia 2 — Vocabulário do domínio e a entidade `Usuario`

**Objetivo:** estabelecer os valores válidos do sistema, a hierarquia de erros e a
primeira entidade com comportamento.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `app/enums.py` | `StatusTarefa`, `PrioridadeTarefa` (com `peso` e `mapa_de_pesos()`), `CampoOrdenacao`, `Ordem` |
| `app/exceptions.py` | `ErroDeDominio` e a hierarquia: `RecursoNaoEncontrado`, `RegraDeNegocioViolada`, `EmailJaCadastrado`, `CredenciaisInvalidas`, `AcessoNaoAutorizado` e as folhas |
| `app/security.py` | `HashDeSenha` (ABC) e `HashBcrypt` |
| `app/models.py` | Apenas `Usuario`: `_senha_hash` privado, `normalizar_email`, `definir_senha`, `senha_confere`, `@validates("nome")` |
| `tests/__init__.py` | Vazio — torna `tests` um pacote |
| `tests/conftest.py` | SQLite em memória, `HashFake`, fixtures `banco_limpo` e `sessao` |
| `tests/test_dominio.py` | As regras do `Usuario`, sem banco |
| `tests/test_banco.py` | A tabela, as colunas e a restrição de e-mail único |
| `tests/test_seguranca.py` | O contrato de hash e o `HashBcrypt` de verdade |

**Decisão a tomar com consciência:** a senha **não** entra pelo construtor. Só
`definir_senha` grava, e ela exige um `HashDeSenha`. É o que torna impossível gravar
senha em texto puro por descuido (RN-05).

**Como verificar**

```bash
python -m pytest -q          # 35 passed
```

- **35 testes verdes**, em menos de um segundo.
- A tabela `usuarios` aparece com as 5 colunas — verificado por `test_banco.py`, e
  visível também abrindo o `todo_list.db` em um visualizador de SQLite.
- Gravar a **mesma** senha para dois usuários produz hashes **diferentes** — é o salt do
  bcrypt em ação, e a demonstração mais direta da RN-05. Vale rodar à mão uma vez:

```bash
python -c "from app.security import HashBcrypt; h=HashBcrypt(); print(h.gerar('senha123')); print(h.gerar('senha123'))"
```

**Armadilhas do dia**

- `validates` vem de `sqlalchemy.orm`, não de `sqlalchemy`.
- Declarar `Column(String)` sem tamanho. O SQLite aceita, o PostgreSQL também — mas um
  campo sem limite declarado é uma decisão de projeto por omissão, e quebra no dia em que
  alguém apontar o projeto para o MySQL. Declare `String(n)`.
- SQLite em memória exige `StaticPool`, senão cada operação encontra um banco vazio.
- No `conftest.py`, `DATABASE_URL` tem de ser definida **antes** de importar `app`, porque
  a configuração fica em cache na primeira importação.
- O limite do bcrypt é de 72 **bytes**, não 72 caracteres: 40 caracteres acentuados
  já passam. O bcrypt 4.x corta o excedente em silêncio e o 5.0 levanta `ValueError` —
  por isso `HashBcrypt.gerar` valida o tamanho, o que dá o mesmo comportamento nas duas
  versões.
- Não use `passlib` sobre o bcrypt, embora seja o que a maioria dos tutoriais faz: a
  última versão dele é de 2020 e lê `bcrypt.__about__`, atributo removido no bcrypt 4.1.
  Quem usa os dois é obrigado a fixar `bcrypt<4.1` — e versão fixada em biblioteca de
  criptografia barra as correções de segurança publicadas depois dela.

**Commit:** `Implementa enums, exceções de domínio, hash de senha e a entidade Usuario`

---

## Dia 3 — A entidade `Tarefa` e a RN-03

**Objetivo:** o dia mais importante do roteiro. A regra que governa a data de conclusão
tem de ficar impossível de violar a partir de fora.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `app/models.py` | `Tarefa` completa: `_status` e `_concluido_em` privados, `status` como `hybrid_property` somente leitura, `concluido_em` como propriedade, `concluir`, `reabrir`, `definir_status`, `esta_atrasada`, `pertence_a`, `@validates` de título e prioridade |
| `app/models.py` | E o `Usuario` ganha o `relationship("Tarefa")` e o `tarefas_pendentes()` — que não podiam existir no Dia 2, porque um relacionamento não pode apontar para uma classe que ainda não existe |
| `tests/test_dominio.py` | Completo — **37 testes** (os do `Usuario`, do Dia 2, mais os da `Tarefa`) |
| `tests/test_banco.py` | Ganha os testes da chave estrangeira — a `Tarefa` é a primeira entidade a ter uma |

**Os três casos da RN-03**, que são o coração do dia:

| Transição | Efeito sobre a data de conclusão |
|---|---|
| pendente → concluída | recebe o momento atual |
| concluída → pendente | volta a ser nula |
| concluída → concluída | **não muda** — preserva a data original |

O terceiro caso é o que reprova implementações ingênuas: sem ele, editar o título de uma
tarefa antiga falsifica a data de conclusão.

**Como verificar**

```bash
python -m pytest -q          # 56 passed
```

Ao final do dia a camada de domínio está **completa**: 37 testes de domínio, 7 de banco e
os 12 de segurança do Dia 2.

Três verificações que não podem faltar:

1. `tarefa.status = StatusTarefa.CONCLUIDA` levanta `AttributeError` — não existe setter.
2. Concluir duas vezes preserva a primeira data.
3. `Tarefa(usuario_id=1, titulo="X", status=...)` levanta `TypeError` — não há como criar
   uma tarefa já concluída (RN-02).
4. Inserir uma tarefa com `usuario_id=9999` pela sessão **falha** com `IntegrityError` —
   é o `PRAGMA foreign_keys` do Dia 1 ganhando efeito observável pela primeira vez.

**Armadilhas do dia**

- `hybrid_property` precisa do par `@status.expression` para funcionar dentro de consulta
  SQL; sem ele, o repositório do Dia 4 não consegue filtrar por status.
- Definir `__init__` próprio em modelo declarativo é permitido — o SQLAlchemy não o chama
  ao carregar registros do banco. Mas o `default=` da coluna só vale no flush, então o
  construtor precisa atribuir `_status` explicitamente.
- Tentar validar o status com `@validates` em vez de encapsular: valida o valor, mas não
  garante a relação com a data de conclusão. São problemas diferentes.
- Agora que existe a chave estrangeira `usuario_id`, vale conferir se o `PRAGMA` do Dia 1
  está mesmo ativo. Inserir uma tarefa com `usuario_id=9999` direto pela sessão **tem**
  de falhar. Se passar, o `PRAGMA` não está sendo aplicado — e o erro só apareceria em
  produção.

**Commit:** `Implementa a entidade Tarefa com a RN-02 e a RN-03 encapsuladas`

---

## Dia 4 — Repositórios

**Objetivo:** isolar todo o acesso ao banco em uma camada só.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `app/repositories.py` | `RepositorioBase` (ABC genérica) com `buscar_por_id`, `salvar`, `remover`; `UsuarioRepositorio` com `buscar_por_email` e `email_existe`; `FiltroDeTarefas` (dataclass); `TarefaRepositorio` com `listar` e a ordenação por peso de prioridade |

**Por que uma classe base abstrata aqui:** `buscar_por_id`, `salvar` e `remover` são
idênticos para as duas entidades. Na versão 1.0.0, o trecho de busca-ou-404 aparecia
repetido em quatro endpoints. A herança entra para eliminar repetição que existe de fato.

**Como verificar**

Rode a aplicação com o SQL à vista — basta ligar a variável de ambiente, sem editar
código:

```bash
ECHO_SQL=true uvicorn app.main:app --reload
```

Depois, um script curto no terminal (ou o REPL) que cadastra um usuário, três tarefas com
prioridades diferentes e lista com filtro e ordenação:

- Listar com `ordenar_por=CampoOrdenacao.PRIORIDADE` e `ordem=Ordem.ASC` traz
  **urgente primeiro** — e não em ordem alfabética.
- Filtrar por status devolve apenas as tarefas daquele status.
- No terminal, o `SELECT` gerado mostra o `ORDER BY CASE` — vale ler, é o que traduz a
  prioridade textual em peso.

**Armadilhas do dia**

- Ordenar prioridade pelo texto dá "alta, baixa, media, urgente". É por isso que existe
  o `case()` com o mapa de pesos vindo do enum.
- Comparar coluna com membro de enum: use `.value` na condição, para não depender de
  coerção implícita.
- Deixar o `commit()` fora do repositório e espalhá-lo pelos serviços: a partir daí,
  ninguém mais sabe onde a transação começa e termina.

**Commit:** `Implementa repositórios com filtro e ordenação de tarefas`

---

## Dia 5 — Serviços

**Objetivo:** ter o sistema inteiro funcionando **sem HTTP nenhum**.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `app/services.py` | `NAO_INFORMADO` (sentinela), `AlteracoesDaTarefa`, `UsuarioServico` (`cadastrar`, `autenticar`, `buscar`), `TarefaServico` (`criar`, `listar`, `buscar`, `atualizar`, `remover`) |

**A sentinela merece atenção.** No `PATCH`, é preciso distinguir "não mencionei o prazo"
de "quero apagar o prazo". Um `None` não dá conta das duas coisas — daí o objeto
sentinela e o método `informado()`.

**Como verificar**

Um script que exercita o fluxo completo, sem subir a API:

```python
# cadastrar → autenticar → criar tarefa → concluir → reabrir → remover
# e depois: cadastrar o mesmo e-mail (espera EmailJaCadastrado)
#           criar tarefa para usuário inexistente (espera UsuarioNaoEncontrado)
```

Uma verificação de arquitetura que vale rodar:

```bash
grep -rnE "^[[:space:]]*(from|import)[[:space:]]+fastapi" app/models.py app/services.py app/repositories.py
```

Não deve encontrar nada. Se encontrar, HTTP vazou para dentro do domínio.

> O padrão procura apenas **linhas de import**, de propósito. Um `grep` por `fastapi`
> solto também casa com comentários e docstrings que mencionam a palavra — inclusive a
> deste módulo, que diz justamente que ele não importa `fastapi`.

**Armadilhas do dia**

- Reimplementar a RN-03 no serviço. O serviço só encaminha: quem sabe concluir e reabrir
  é a `Tarefa`. Se a regra aparecer nos dois lugares, uma das cópias vai divergir.
- Levantar `HTTPException` no serviço porque é mais rápido. É o atalho que custa a
  reutilização do domínio fora da web.

**Commit:** `Implementa serviços de usuário e tarefa com as regras de negócio`

---

## Dia 6 — Borda HTTP

**Objetivo:** expor os 7 endpoints, traduzindo entre o mundo do cliente e o do domínio.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `app/schemas.py` | `EsquemaDeEntrada` e `EsquemaDeSaida` (com `alias_generator=to_camel`), os schemas de usuário e de tarefa |
| `app/dependencies.py` | `obter_hasher`, `obter_usuario_servico`, `obter_tarefa_servico` |
| `app/routers/usuarios.py` | 3 rotas, de 1 linha de corpo cada |
| `app/routers/tasks.py` | 4 rotas e `_montar_alteracoes` |
| `app/main.py` | `STATUS_POR_ERRO`, o tratador de `ErroDeDominio`, CORS e o registro dos routers |

**A tradução de nomes acontece aqui, e só aqui.** O Python escreve `usuario_id`; o JSON
devolve `usuarioId`. O `alias_generator` faz a ponte, e `populate_by_name=True` aceita as
duas formas na entrada.

**O tratador de erros é onde o polimorfismo se paga:** um único `@app.exception_handler`
registrado para `ErroDeDominio` atende a hierarquia inteira, porque o Starlette percorre a
MRO da exceção. Exceção nova, desde que herde da classe certa, já sai com o código certo.

**Como verificar**

Pelo `/docs`, na sequência: cadastrar usuário → repetir o cadastro (409) → login com
senha errada (401) → criar tarefa → concluir (`concluidoEm` preenchido) → editar só o
título (`concluidoEm` **inalterado**) → listar com `?status=concluida` → remover (204) →
remover de novo (404).

Confirmar também que os campos da resposta estão em **camelCase**.

**Armadilhas do dia**

- Usar `Query()` como valor padrão em parâmetro de tipo união. Prefira
  `Annotated[StatusTarefa | None, Query(alias="status")] = None`, que é a forma
  recomendada hoje.
- Esquecer `exclude_unset=True` no `model_dump()`: todo campo ausente chega como `None` e
  o `PATCH` apaga o que não foi mencionado.
- Devolver corpo em uma resposta 204.
- Registrar o tratador para cada exceção concreta, uma por uma, em vez de registrar para a
  classe base.

**Commit:** `Expõe os 7 endpoints e traduz erros de domínio em códigos HTTP`

---

## Dia 7 — Testes, documentação e fechamento

**Objetivo:** automatizar o que foi verificado à mão e deixar o projeto entregável.

**O que construir**

| Arquivo | Conteúdo |
|---|---|
| `tests/test_api.py` | **28 testes**: endpoints, códigos de status e o contrato JSON |
| `tests/test_configuracao.py` | **19 testes**: escolha do banco e normalização da URL |
| `tests/test_banco.py` | **5 testes**: chave estrangeira e restrições de unicidade |
| `pytest.ini` | `testpaths` e os `filterwarnings` justificados |
| `README.md` | Pré-requisitos, instalação, banco, arquitetura, endpoints, exemplos e limitações |
| `docs/manual_tecnico.md` | Documentação técnica completa |

**Cinco testes que não podem faltar**, porque protegem o que é fácil quebrar depois:

1. Editar o título de uma tarefa concluída **não** altera `concluidoEm` (RN-03 de ponta a
   ponta, atravessando as quatro camadas).
2. A resposta usa camelCase e **não** contém `senha` nem `senhaHash`.
3. `?ordenarPor=inventado` devolve 422 — e não uma ordenação silenciosamente trocada.
4. Inserir tarefa com `usuario_id` inexistente direto pela sessão é **recusado pelo
   banco** — prova que o `PRAGMA foreign_keys` está ativo.
5. Uma URL `postgres://` é normalizada para o driver do projeto — prova que a aplicação
   aceita a credencial como a hospedagem entrega.

**Como verificar**

```bash
python -m pytest -q          # 109 passed
```

- A suíte roda **sem nenhum banco instalado**.
- Os exemplos do README devem ser copiados de uma execução real, não escritos de memória.
- Vale gerar o DDL nos dois dialetos e comparar, para confirmar que os modelos são
  portáveis entre SQLite e PostgreSQL sem alteração.

**Armadilhas do dia**

- `TestClient(app)` sem `with` não executa o `lifespan`. É o que se quer aqui, porque
  quem cria as tabelas é a fixture — mas é preciso saber disso.
- Trocar o `HashBcrypt` pelo `HashFake` via `dependency_overrides`: sem isso, a suíte
  paga o custo do bcrypt em cada teste.
- Testar a configuração pela função com cache (`obter_configuracao`) em vez de
  `Configuracao.do_ambiente()`: o cache guarda o primeiro resultado e o `monkeypatch` da
  variável de ambiente não tem efeito.
- Avisos do Pydantic sobre `Field()` em campos de tipo união vêm da combinação
  FastAPI 0.115 + Pydantic 2.13, **não** do código do projeto. Reproduzem-se com qualquer
  `response_model` que tenha um campo `X | None`.

**Commit:** `Adiciona suíte de testes automatizados e documentação`

---

## Se o tempo apertar

Cortar na ordem inversa da importância. O caminho mínimo para um sistema **correto**,
ainda que menos completo:

| Prioridade | O que é | Pode ficar para depois? |
|---|---|---|
| 1 | Dias 1 a 3 — infraestrutura e domínio com a RN-03 testada | Não. É o que garante que o sistema não corrompe dados |
| 2 | Dias 5 e 6 — serviços e endpoints | Não. Sem eles não há API |
| 3 | Dia 4 — filtros e ordenação | Sim. Um `listar` simples por usuário já entrega valor |
| 4 | Dia 7 — os 28 testes de API e os 19 de configuração | Parcialmente. Os 5 testes citados acima são o mínimo |
| 5 | Manual técnico completo | Sim, desde que o README fique pronto |

O que **não** se corta: os 22 testes de domínio do Dia 3 e o teste de chave estrangeira
do Dia 7. São baratos, rápidos e protegem as duas únicas formas de o sistema gravar
informação errada no banco em silêncio.

---

## Preparar para produção

O roteiro entrega um sistema que roda. Para colocá-lo no ar, três passos — nenhum deles
exige alterar código da aplicação:

1. **Criar o banco PostgreSQL** na plataforma escolhida e copiar a URL de conexão.
2. **Definir as variáveis de ambiente** no painel da plataforma:
   `DATABASE_URL` (a URL do banco) e `ORIGENS_PERMITIDAS` (o domínio do front-end).
3. **Subir a aplicação** com `uvicorn app.main:app`, sem `--reload`.

O que ainda **falta** para que isso seja responsável, e está registrado como limitação
conhecida no README: autenticação por token. Sem ela, os endpoints de tarefa confiam no
`usuarioId` que o cliente enviar.

---

## Relação com o PTD da UC 12

Este roteiro cobre o mesmo escopo das **Aulas 17 a 24** (Fase 3 — Projeto Integrador),
com um recorte diferente: sete blocos por camada, em vez de oito aulas de quatro horas.

| Dia deste roteiro | Aula correspondente no PTD |
|---|---|
| 1 | Aula 17 — configuração, conexão e modelagem |
| 2 e 3 | Aula 17 (modelos) reaproveitando a Fase 2, Aulas 13 a 16 |
| 4 e 5 | Aulas 19 e 20 — CRUD, regras de negócio e filtros |
| 6 | Aulas 18 e 19 — schemas, segurança e endpoints |
| 7 | Aulas 22 e 23 — testes e documentação |

> **Ressalva importante.** A Fase 3 do PTD descreve a **versão 1.0.0** do projeto em dois
> aspectos que mudaram: a arquitetura (modelos sem comportamento, regras de negócio
> dentro das funções de rota) e o banco de dados (MySQL em servidor, instalado na Aula
> 17). Este roteiro constrói a versão 2.1.0, em camadas e com SQLite no desenvolvimento.
>
> A troca de banco tem uma consequência curricular que o docente precisa considerar: o
> **Indicador 5** da UC exige integração com banco "de acordo com premissas do sistema
> operacional (servidor) de rede". O PostgreSQL de produção atende; o SQLite de
> desenvolvimento, não — ele é arquivo local. Se a turma nunca apontar o projeto para um
> banco em servidor, a evidência desse indicador fica fraca. A sincronização do PTD e da
> documentação técnica com a arquitetura e o banco atuais está pendente.

---

## Checklist de entrega

- [ ] `uvicorn app.main:app --reload` sobe sem erro e `/docs` lista os 7 endpoints
- [ ] Com o `.env.example` copiado para `.env`, a aplicação sobe e cria o `todo_list.db`
- [ ] **Sem** `DATABASE_URL` definida, a aplicação recusa subir com uma mensagem que diz
      onde o `.env` foi procurado — não há banco padrão silencioso
- [ ] `python -m pytest` devolve 109 testes verdes ao fim do Dia 7 (138 no repositório
      completo, que inclui a camada de integração da 2.2.0)
- [ ] A suíte roda sem nenhum banco de dados instalado
- [ ] `grep -rnE "^[[:space:]]*(from|import)[[:space:]]+fastapi" app/models.py app/services.py app/repositories.py` não acha nada
- [ ] `tarefa.status = ...` levanta `AttributeError`
- [ ] Editar o título de uma tarefa concluída preserva `concluidoEm`
- [ ] Inserir tarefa com `usuario_id` inexistente é recusado pelo banco
- [ ] Uma URL `postgres://` é aceita e normalizada
- [ ] Nenhuma resposta da API contém `senha` ou `senhaHash`
- [ ] `git status` não lista o `.env` nem o `todo_list.db`, e o histórico tem ao menos um commit por dia
- [ ] README com pré-requisitos, instalação, banco, arquitetura e limitações conhecidas
- [ ] As limitações estão registradas: sem JWT, e **nenhum** endpoint verificando a
      identidade de quem chama — inclusive os de leitura, `GET /tasks` e `GET /usuarios/{id}`
