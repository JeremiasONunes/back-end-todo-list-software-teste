"""Provedores de dependência: montam os objetos que as rotas usam.

Concentrar a montagem aqui tem um efeito prático: a rota declara que precisa
de um `TarefaServico` e não sabe quantas peças existem por trás dele. Se
amanhã o serviço passar a receber um colaborador novo, muda este módulo — e
nenhuma rota.

É também onde mora a dependência de autenticação. Uma rota que declara
`Annotated[Usuario, Depends(obter_usuario_autenticado)]` passa a exigir token:
não há como esquecer a verificação, porque sem ela não há de onde tirar o
usuário.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Configuracao, obter_configuracao
from app.database import obter_sessao
from app.exceptions import NaoAutenticado, UsuarioNaoEncontrado
from app.models import Usuario
from app.repositories import TarefaRepositorio, UsuarioRepositorio
from app.security import HashBcrypt, HashDeSenha
from app.services import TarefaServico, UsuarioServico
from app.tokens import TokenDeAcesso, validade_a_partir_de_horas

#: Extrai o token do cabeçalho `Authorization: Bearer <token>`.
#:
#: `auto_error=False` desliga a resposta automática do FastAPI, que devolveria
#: 403 com um corpo em inglês quando o cabeçalho falta. Preferimos detectar a
#: ausência e levantar `NaoAutenticado`, que responde **401** — o código que
#: descreve "não sei quem você é", enquanto 403 significa "sei quem você é e
#: não pode" — e com o mesmo formato de erro das demais respostas da API.
esquema_bearer = HTTPBearer(auto_error=False, description="Token obtido no login")


def obter_hasher() -> HashDeSenha:
    """Implementação de hash usada pela aplicação.

    Declarada como dependência — e não instanciada direto no serviço — para
    poder ser substituída nos testes por uma implementação instantânea.
    """
    return HashBcrypt()


def obter_token_de_acesso(
    configuracao: Annotated[Configuracao, Depends(obter_configuracao)],
) -> TokenDeAcesso:
    """Emissor e leitor de tokens, com o segredo e a validade do ambiente."""
    return TokenDeAcesso(
        segredo=configuracao.segredo_jwt,
        validade=validade_a_partir_de_horas(
            configuracao.validade_do_token_em_horas
        ),
    )


def obter_usuario_servico(
    sessao: Session = Depends(obter_sessao),
    hasher: HashDeSenha = Depends(obter_hasher),
) -> UsuarioServico:
    """Serviço de usuários, com repositório e hasher já injetados."""
    return UsuarioServico(UsuarioRepositorio(sessao), hasher)


def obter_tarefa_servico(
    sessao: Session = Depends(obter_sessao),
) -> TarefaServico:
    """Serviço de tarefas, com os dois repositórios de que depende."""
    return TarefaServico(TarefaRepositorio(sessao), UsuarioRepositorio(sessao))


def obter_usuario_autenticado(
    credenciais: Annotated[
        HTTPAuthorizationCredentials | None, Depends(esquema_bearer)
    ],
    tokens: Annotated[TokenDeAcesso, Depends(obter_token_de_acesso)],
    servico: Annotated[UsuarioServico, Depends(obter_usuario_servico)],
) -> Usuario:
    """Devolve o usuário que o token identifica.

    O usuário é buscado no banco a cada requisição, em vez de ser reconstruído
    a partir do conteúdo do token. São dois motivos:

    1. Uma conta apagada deixa de funcionar imediatamente. Confiando apenas no
       token, ela continuaria válida até a expiração.
    2. Nome e e-mail vêm sempre atualizados. Se estivessem no token, uma troca
       de e-mail só apareceria no próximo login.

    O custo é uma consulta por requisição — a mesma que um token opaco com
    sessão em tabela exigiria, e por isso parte da economia prometida pelo JWT
    não se realiza aqui. O que se ganha mesmo assim é não precisar de tabela de
    sessões nem de rotina de limpeza.

    Raises:
        NaoAutenticado: sem cabeçalho `Authorization`, com token inválido, ou
            com token válido de uma conta que não existe mais.
        SessaoExpirada: token vencido (levantada por `TokenDeAcesso.ler`).
    """
    if credenciais is None:
        raise NaoAutenticado()

    usuario_id = tokens.ler(credenciais.credentials)

    try:
        return servico.buscar(usuario_id)
    except UsuarioNaoEncontrado as erro:
        # A conta foi apagada depois da emissão do token. Responder 404 diria
        # que o *recurso* não existe, quando o problema é que a sessão não
        # identifica mais ninguém — o que é 401, e é o que faz o cliente
        # limpar o token e pedir login outra vez.
        raise NaoAutenticado() from erro
