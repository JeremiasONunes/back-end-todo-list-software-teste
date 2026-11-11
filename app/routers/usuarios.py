"""Endpoints de usuário: cadastro, login e consulta da própria conta.

Compare com a versão anterior: não há consulta ao banco, não há `if` de regra
de negócio e não há `raise HTTPException`. A rota traduz HTTP em uma chamada de
serviço e devolve o resultado. Os erros de negócio sobem como exceções de
domínio e são convertidos em código de status por `main.py`.

Dois dos três endpoints são **públicos**, e precisam ser: não há como exigir
token de quem está criando a conta ou tentando entrar nela. São os únicos da
API nessa condição.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import (
    obter_token_de_acesso,
    obter_usuario_autenticado,
    obter_usuario_servico,
)
from app.models import Usuario
from app.schemas import SessaoOut, UsuarioCreate, UsuarioLogin, UsuarioOut
from app.services import UsuarioServico
from app.tokens import TokenDeAcesso

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def _abrir_sessao(usuario: Usuario, tokens: TokenDeAcesso) -> SessaoOut:
    """Monta a resposta de cadastro e de login a partir do usuário.

    As duas operações terminam igual — uma conta autenticada e um token para
    usá-la —, e a diferença entre elas está apenas em como se chega ao usuário.
    """
    return SessaoOut(access_token=tokens.emitir(usuario.id), usuario=usuario)


@router.post(
    "",
    response_model=SessaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar usuário",
    responses={409: {"description": "E-mail já cadastrado"}},
)
def cadastrar_usuario(
    dados: UsuarioCreate,
    servico: Annotated[UsuarioServico, Depends(obter_usuario_servico)],
    tokens: Annotated[TokenDeAcesso, Depends(obter_token_de_acesso)],
) -> SessaoOut:
    """Cadastra um usuário e já devolve a sessão aberta.

    O token vem junto porque quem acabou de criar a conta está autenticado por
    definição: exigir um login imediatamente depois seria pedir a mesma senha
    duas vezes seguidas.
    """
    usuario = servico.cadastrar(dados.nome, dados.email, dados.senha)
    return _abrir_sessao(usuario, tokens)


@router.post(
    "/login",
    response_model=SessaoOut,
    summary="Autenticar usuário",
    responses={401: {"description": "E-mail ou senha inválidos"}},
)
def autenticar_usuario(
    dados: UsuarioLogin,
    servico: Annotated[UsuarioServico, Depends(obter_usuario_servico)],
    tokens: Annotated[TokenDeAcesso, Depends(obter_token_de_acesso)],
) -> SessaoOut:
    """Confere e-mail e senha e devolve o token de acesso."""
    usuario = servico.autenticar(dados.email, dados.senha)
    return _abrir_sessao(usuario, tokens)


@router.get(
    "/eu",
    response_model=UsuarioOut,
    summary="Consultar a própria conta",
    responses={401: {"description": "Token ausente, inválido ou expirado"}},
)
def consultar_conta(
    usuario: Annotated[Usuario, Depends(obter_usuario_autenticado)],
) -> UsuarioOut:
    """Retorna os dados do usuário autenticado.

    Substitui o antigo `GET /usuarios/{id}`, que devolvia nome, e-mail e data
    de cadastro de **qualquer** usuário a **qualquer** cliente. Como os ids são
    inteiros sequenciais, bastava percorrer `1, 2, 3…` para coletar a base
    inteira de e-mails.

    O endpoint existe para o cliente reconstruir a sessão ao abrir o
    aplicativo: ele guarda o token, não o usuário, e pergunta aqui quem é o
    dono do token que tem em mãos.
    """
    return usuario
