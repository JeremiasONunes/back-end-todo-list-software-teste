"""Ponto de entrada: cria o app, registra as rotas e traduz erros em HTTP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import obter_configuracao
from app.database import criar_tabelas
from app.exceptions import (
    AcessoNaoAutorizado,
    CredenciaisInvalidas,
    EmailJaCadastrado,
    ErroDeDominio,
    NaoAutenticado,
    RecursoNaoEncontrado,
    RegraDeNegocioViolada,
)
from app.routers import tasks, usuarios
from app.routers.tasks import CABECALHO_TOTAL
from app.validacao import descrever

# Cada família de erro de domínio corresponde a um código HTTP. A ordem
# importa: vale o primeiro tipo que casar, do mais específico ao mais geral.
STATUS_POR_ERRO: tuple[tuple[type[ErroDeDominio], int], ...] = (
    (RecursoNaoEncontrado, 404),
    (EmailJaCadastrado, 409),
    (CredenciaisInvalidas, 401),
    # `NaoAutenticado` cobre também `SessaoExpirada`, que herda dela: as duas
    # respondem 401 e só diferem na mensagem. 401 é "não sei quem você é";
    # `AcessoNaoAutorizado`, logo abaixo, é "sei quem você é e não pode".
    (NaoAutenticado, 401),
    (AcessoNaoAutorizado, 403),
    (RegraDeNegocioViolada, 422),
    (ErroDeDominio, 400),
)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    """Prepara o banco na subida da aplicação e libera recursos na descida."""
    criar_tabelas()
    yield


app = FastAPI(
    title="Todo List API",
    description=(
        "Backend de gerenciamento de tarefas, com autenticação por token JWT. "
        "Projeto Integrador da UC 12 — Técnico em Informática, SENAC Minas.\n\n"
        "Para experimentar pelo `/docs`: cadastre-se ou entre em "
        "`POST /usuarios/login`, copie o `accessToken` da resposta e informe-o "
        "no botão **Authorize** — os endpoints de `/tasks` exigem esse token."
    ),
    version="3.0.0",
    lifespan=ciclo_de_vida,
)

# Sem esta configuração, um front-end rodando em outro endereço teria suas
# requisições bloqueadas pelo navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(obter_configuracao().origens_permitidas),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sem declarar aqui, o navegador deixa o JavaScript ler apenas um punhado
    # de cabeçalhos padrão — e `X-Total-Count` chegaria na resposta mas sairia
    # como `null` no `fetch`. É uma restrição do CORS, não um erro da API.
    expose_headers=[CABECALHO_TOTAL],
)


@app.exception_handler(ErroDeDominio)
async def tratar_erro_de_dominio(
    _request: Request, excecao: ErroDeDominio
) -> JSONResponse:
    """Converte qualquer erro de domínio na resposta HTTP correspondente.

    Um único tratador atende a hierarquia inteira de exceções — é polimorfismo
    aplicado ao tratamento de erro. O resultado prático é que as rotas não
    precisam conhecer códigos de status de negócio e o domínio não precisa
    conhecer HTTP. Uma exceção nova, desde que herde da classe certa, já chega
    ao cliente com o código adequado sem alterar nada aqui.
    """
    for tipo, codigo in STATUS_POR_ERRO:
        if isinstance(excecao, tipo):
            return JSONResponse(
                status_code=codigo, content={"detail": excecao.mensagem}
            )
    return JSONResponse(status_code=400, content={"detail": excecao.mensagem})


@app.exception_handler(RequestValidationError)
async def tratar_erro_de_validacao(
    _request: Request, excecao: RequestValidationError
) -> JSONResponse:
    """Reduz o erro de validação do Pydantic a uma única frase legível.

    Por padrão, o FastAPI responde 422 com `detail` sendo uma **lista de
    objetos**, um por campo recusado. Os erros de domínio desta API respondem
    com `detail` sendo um **texto**. Quem consome a API teria então de tratar
    dois formatos no mesmo campo — e um cliente que exibe a mensagem
    diretamente na tela mostraria `[object Object]` no primeiro caso.

    Aqui os dois passam a ter a mesma forma: `detail` é sempre uma frase. A
    lista original continua disponível em `erros`, que é o que serve para
    depurar e para destacar o campo errado em um formulário.

    A frase também é traduzida para português (ver `app/validacao.py`): o
    cliente mostra esta mensagem direto na tela, e uma interface em português
    não deveria exibir `String should have at least 1 character`.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": descrever(excecao.errors()),
            "erros": jsonable_encoder(excecao.errors()),
        },
    )


app.include_router(usuarios.router)
app.include_router(tasks.router)


@app.get("/", tags=["Status"], summary="Verificar se a API está no ar")
def raiz() -> dict[str, str]:
    """Confirma que a API está no ar e indica onde está a documentação."""
    return {"mensagem": "Todo List API no ar", "documentacao": "/docs"}
