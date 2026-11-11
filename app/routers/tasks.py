"""Endpoints de tarefas: criação, listagem com filtros, atualização e exclusão.

Os nomes públicos dos parâmetros de consulta continuam em camelCase
(`prazoAte`, `ordenarPor`), preservando o contrato com o front-end, mas do lado
do Python são `snake_case` — o `alias` faz a ponte.

**Todos os endpoints deste módulo exigem autenticação**, e o dono das tarefas é
sempre o usuário do token. Não existe parâmetro para dizer "as tarefas de
alguém": é o que torna impossível pedir as de outra pessoa.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BeforeValidator

from app.dependencies import obter_tarefa_servico, obter_usuario_autenticado
from app.enums import (
    CampoOrdenacao,
    Ordem,
    PrioridadeTarefa,
    StatusTarefa,
    ignorar_sentinela_de_filtro,
)
from app.models import Usuario
from app.repositories import FiltroDeTarefas
from app.schemas import TarefaCreate, TarefaOut, TarefaUpdate
from app.services import AlteracoesDaTarefa, TarefaServico

#: A dependência de autenticação é declarada no router, e não em cada função.
#:
#: Assim um endpoint novo nasce protegido: esquecer de pedir o usuário deixa a
#: rota sem acesso ao dono das tarefas, e não aberta ao mundo. O padrão oposto
#: — proteger rota por rota — falha pelo esquecimento de uma só.
router = APIRouter(
    prefix="/tasks",
    tags=["Tarefas"],
    responses={401: {"description": "Token ausente, inválido ou expirado"}},
)

#: Aplicado aos filtros opcionais: converte a sentinela "todas" do cliente em
#: `None` **antes** da validação do enum, que de outro modo recusaria o valor
#: com 422. Fica no `Annotated` do parâmetro para que a documentação do
#: OpenAPI continue listando os valores válidos do enum.
SemFiltro = BeforeValidator(ignorar_sentinela_de_filtro)

#: Nome do cabeçalho com o total de tarefas que atendem ao filtro.
#:
#: O total vai no cabeçalho, e não no corpo, de propósito: trocar o corpo por
#: `{"total": 120, "itens": [...]}` quebraria todo cliente que já consome a
#: resposta como um array -- e é exatamente assim que o front-end a consome.
CABECALHO_TOTAL = "X-Total-Count"

#: Tipo do usuário autenticado, para não repetir o `Annotated` em cada rota.
UsuarioAutenticado = Annotated[Usuario, Depends(obter_usuario_autenticado)]


def _montar_alteracoes(dados: TarefaUpdate) -> AlteracoesDaTarefa:
    """Converte o corpo do PATCH em alterações de domínio.

    `exclude_unset=True` devolve apenas os campos que o cliente realmente
    enviou. Os ausentes ficam com a sentinela `NAO_INFORMADO`, o que permite
    distinguir "não mencionei o prazo" de "quero apagar o prazo".
    """
    return AlteracoesDaTarefa(**dados.model_dump(exclude_unset=True))


@router.post(
    "",
    response_model=TarefaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tarefa",
)
def criar_task(
    dados: TarefaCreate,
    usuario: UsuarioAutenticado,
    servico: Annotated[TarefaServico, Depends(obter_tarefa_servico)],
) -> TarefaOut:
    """Cria uma tarefa para o usuário autenticado. Nasce sempre pendente.

    O dono vem do token, não do corpo da requisição. Some com isso a
    possibilidade de criar tarefa no nome de outra pessoa — e também o 404 de
    "usuário não encontrado", que não tem mais como acontecer: o usuário do
    token já foi carregado do banco para chegar até aqui.
    """
    return servico.criar(
        usuario_id=usuario.id,
        titulo=dados.titulo,
        prioridade=dados.prioridade,
        prazo=dados.prazo,
    )


@router.get(
    "",
    response_model=list[TarefaOut],
    summary="Listar as próprias tarefas",
)
def listar_tasks(
    resposta: Response,
    usuario: UsuarioAutenticado,
    servico: Annotated[TarefaServico, Depends(obter_tarefa_servico)],
    status_tarefa: Annotated[
        StatusTarefa | None, SemFiltro, Query(alias="status")
    ] = None,
    prioridade: Annotated[PrioridadeTarefa | None, SemFiltro, Query()] = None,
    prazo_ate: Annotated[
        date | None,
        Query(alias="prazoAte", description="Somente tarefas com prazo até esta data"),
    ] = None,
    busca: Annotated[
        str | None,
        Query(description="Filtra pelo título, sem diferenciar maiúsculas"),
    ] = None,
    ordenar_por: Annotated[
        CampoOrdenacao, Query(alias="ordenarPor")
    ] = CampoOrdenacao.CRIADO_EM,
    ordem: Annotated[Ordem | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=200, alias="limit")] = 50,
    deslocamento: Annotated[int, Query(ge=0, alias="offset")] = 0,
) -> list[TarefaOut]:
    """Lista as tarefas do usuário autenticado, com filtros e ordenação.

    Devolve uma lista vazia — e não 404 — quando nenhuma tarefa corresponde
    aos critérios: a coleção existe, apenas está vazia.

    Omitir `ordem` não significa decrescente: significa "use o sentido natural
    do campo escolhido" — as mais recentes primeiro em `criadoEm`, o prazo
    mais próximo primeiro em `prazo`, a urgente primeiro em `prioridade`.

    O cabeçalho `X-Total-Count` traz quantas tarefas atendem ao filtro
    ignorando `limit` e `offset`, para que o cliente saiba quando a página
    recebida não é tudo.
    """
    filtro = FiltroDeTarefas(
        usuario_id=usuario.id,
        status=status_tarefa,
        prioridade=prioridade,
        prazo_ate=prazo_ate,
        busca=busca,
        ordenar_por=ordenar_por,
        ordem=ordem,
        limite=limite,
        deslocamento=deslocamento,
    )
    tarefas = servico.listar(filtro)
    resposta.headers[CABECALHO_TOTAL] = str(servico.contar(filtro))
    return tarefas


@router.patch(
    "/{tarefa_id}",
    response_model=TarefaOut,
    summary="Atualizar tarefa",
    responses={
        403: {"description": "A tarefa pertence a outro usuário"},
        404: {"description": "Tarefa não encontrada"},
    },
)
def atualizar_task(
    tarefa_id: int,
    dados: TarefaUpdate,
    usuario: UsuarioAutenticado,
    servico: Annotated[TarefaServico, Depends(obter_tarefa_servico)],
) -> TarefaOut:
    """Atualiza parcialmente uma tarefa do usuário autenticado.

    Quando o status muda, a data de conclusão é ajustada pela própria tarefa,
    conforme a RN-03.
    """
    return servico.atualizar(tarefa_id, _montar_alteracoes(dados), usuario.id)


@router.delete(
    "/{tarefa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover tarefa",
    responses={
        403: {"description": "A tarefa pertence a outro usuário"},
        404: {"description": "Tarefa não encontrada"},
    },
)
def remover_task(
    tarefa_id: int,
    usuario: UsuarioAutenticado,
    servico: Annotated[TarefaServico, Depends(obter_tarefa_servico)],
) -> Response:
    """Remove definitivamente uma tarefa do usuário autenticado."""
    servico.remover(tarefa_id, usuario.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
