"""Enumerações do domínio.

Antes, os valores válidos de status e prioridade estavam escritos como texto
solto em três lugares: no `Literal` dos schemas, no `default` das colunas e no
`case` que ordenava por prioridade. Acrescentar uma prioridade nova exigia
lembrar dos três. Aqui eles passam a ter um único lugar de definição.

Herdar de `str` faz cada membro se comportar como o próprio texto — o que
permite gravá-lo em uma coluna `String`, compará-lo com uma string vinda do
banco e serializá-lo em JSON sem conversão manual.
"""

from __future__ import annotations

from enum import Enum


class StatusTarefa(str, Enum):
    """Situação em que uma tarefa pode estar."""

    PENDENTE = "pendente"
    CONCLUIDA = "concluida"


class PrioridadeTarefa(str, Enum):
    """Nível de prioridade de uma tarefa, da menor para a maior."""

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"

    @property
    def peso(self) -> int:
        """Posição na ordenação por prioridade — 0 é a mais urgente.

        Ordenar pelo texto daria "alta, baixa, media, urgente", que não é a
        ordem que o usuário espera ver. O peso existe para isso.
        """
        return _PESOS[self]

    @classmethod
    def mapa_de_pesos(cls) -> dict[str, int]:
        """Mapa `valor -> peso`, no formato que o `case()` do SQL consome."""
        return {prioridade.value: prioridade.peso for prioridade in cls}


_PESOS = {
    PrioridadeTarefa.URGENTE: 0,
    PrioridadeTarefa.ALTA: 1,
    PrioridadeTarefa.MEDIA: 2,
    PrioridadeTarefa.BAIXA: 3,
}


class CampoOrdenacao(str, Enum):
    """Campos pelos quais a listagem de tarefas pode ser ordenada.

    Os valores repetem o nome público do campo na API (camelCase), porque é
    isso que o cliente envia em `?ordenarPor=`. Como é um enum, um valor fora
    da lista passa a ser recusado com 422 — antes, o código caía
    silenciosamente na ordenação por data de criação e o cliente nunca sabia
    que seu parâmetro havia sido ignorado.
    """

    CRIADO_EM = "criadoEm"
    PRAZO = "prazo"
    PRIORIDADE = "prioridade"

    @classmethod
    def _missing_(cls, valor: object) -> CampoOrdenacao | None:
        """Aceita o vocabulário do front-end como apelido do campo canônico.

        O `useTasks.js` chama de `recente` o que aqui se chama `criadoEm`: é o
        mesmo critério visto de ângulos diferentes — o cliente nomeia o
        resultado ("as mais recentes primeiro") e a API nomeia a coluna.
        Traduzir aqui evita um 422 em uma requisição que pede exatamente o que
        a API já sabe fazer.

        `_missing_` é consultado pelo `Enum` quando nenhum membro corresponde
        ao valor recebido, e é por onde o Pydantic passa ao validar o
        parâmetro de consulta. Devolver `None` preserva o 422 para o que
        continua sendo inválido de fato.
        """
        if isinstance(valor, str) and valor.strip().lower() == "recente":
            return cls.CRIADO_EM
        return None

    @property
    def ordem_natural(self) -> Ordem:
        """Sentido esperado deste campo quando o cliente não pede nenhum.

        Um padrão único para os três campos acertaria em um e erraria em dois:
        ordenar por prazo de forma decrescente mostraria primeiro o que vence
        por último, e por prioridade mostraria a baixa antes da urgente. Daí
        cada campo declarar o seu.
        """
        return _ORDENS_NATURAIS[self]


class Ordem(str, Enum):
    """Sentido da ordenação."""

    ASC = "asc"
    DESC = "desc"


#: Sentido padrão de cada campo de ordenação. Reproduz o que a função
#: `ordenar()` do `useTasks.js` já fazia no cliente.
_ORDENS_NATURAIS = {
    CampoOrdenacao.CRIADO_EM: Ordem.DESC,
    CampoOrdenacao.PRAZO: Ordem.ASC,
    CampoOrdenacao.PRIORIDADE: Ordem.ASC,
}


#: Valores com que o front-end diz "não filtre por este campo".
#:
#: Os seletores de status e prioridade começam em `todas` e mandam esse valor
#: na requisição, em vez de omitir o parâmetro. Recusá-lo com 422 obrigaria
#: todo cliente a limpar o filtro antes de cada chamada; traduzi-lo para "sem
#: filtro" resolve no único ponto que precisa conhecer essa convenção.
SENTINELAS_SEM_FILTRO = frozenset({"todas", "todos"})


def ignorar_sentinela_de_filtro(valor: object) -> object:
    """Troca a sentinela de "sem filtro" do cliente por `None`.

    Também trata o parâmetro enviado vazio (`?status=`), que tem o mesmo
    significado e chegaria como string vazia.
    """
    if not isinstance(valor, str):
        return valor
    normalizado = valor.strip().lower()
    if not normalizado or normalizado in SENTINELAS_SEM_FILTRO:
        return None
    return valor
