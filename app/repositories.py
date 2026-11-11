"""Repositórios: a única camada que conversa com o banco de dados.

Antes, as consultas estavam escritas dentro das funções de rota. Isso
misturava três assuntos em uma função só — HTTP, regra de negócio e SQL — e
repetia o mesmo trecho de busca-ou-404 em quatro endpoints.

Com os repositórios, a regra passa a ser: serviço não sabe SQL, rota não sabe
banco. Quem precisa de dados pede a um repositório.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Generic, TypeVar

from sqlalchemy import case, nullslast
from sqlalchemy.orm import Session

from app.enums import CampoOrdenacao, Ordem, PrioridadeTarefa, StatusTarefa
from app.models import Tarefa, Usuario

Entidade = TypeVar("Entidade")


class RepositorioBase(ABC, Generic[Entidade]):
    """Operações comuns a qualquer repositório.

    Classe abstrata que funciona como interface: obriga cada repositório
    concreto a declarar qual modelo administra e, em troca, entrega prontas as
    operações que não mudam de entidade para entidade. É herança usada para o
    que ela serve — eliminar repetição real, não para criar hierarquia.
    """

    def __init__(self, sessao: Session) -> None:
        self._sessao = sessao

    @property
    @abstractmethod
    def modelo(self) -> type[Entidade]:
        """Classe do modelo administrado por este repositório."""

    def buscar_por_id(self, identificador: int) -> Entidade | None:
        """Devolve a entidade com o id informado, ou `None`."""
        return self._sessao.get(self.modelo, identificador)

    def salvar(self, entidade: Entidade) -> Entidade:
        """Persiste a entidade e devolve-a já sincronizada com o banco."""
        self._sessao.add(entidade)
        self._sessao.commit()
        self._sessao.refresh(entidade)
        return entidade

    def remover(self, entidade: Entidade) -> None:
        """Apaga a entidade definitivamente."""
        self._sessao.delete(entidade)
        self._sessao.commit()


class UsuarioRepositorio(RepositorioBase[Usuario]):
    """Acesso aos dados de usuário."""

    @property
    def modelo(self) -> type[Usuario]:
        return Usuario

    def buscar_por_email(self, email: str) -> Usuario | None:
        """Busca pelo e-mail, normalizado como o modelo normaliza ao gravar.

        Sem a normalização, um cadastro feito com `"Ana@Exemplo.com"` não seria
        encontrado por uma busca com `"ana@exemplo.com"`.
        """
        return (
            self._sessao.query(Usuario)
            .filter(Usuario.email == Usuario.normalizar_email(email))
            .first()
        )

    def email_existe(self, email: str) -> bool:
        """Informa se já há usuário cadastrado com este e-mail (RN-01)."""
        return self.buscar_por_email(email) is not None


def _escapar_curingas(termo: str) -> str:
    """Neutraliza os curingas do `LIKE` para que a busca seja literal.

    No SQL, `%` significa "qualquer sequência de caracteres" e `_` significa
    "um caractere qualquer". Sem escapá-los, procurar por `100%` devolveria
    todas as tarefas do usuário, e procurar por `a_b` casaria com `aXb`.
    """
    for caractere in ("\\", "%", "_"):
        termo = termo.replace(caractere, f"\\{caractere}")
    return termo


@dataclass(frozen=True)
class FiltroDeTarefas:
    """Critérios de uma consulta de tarefas.

    Existe para que a assinatura de `TarefaRepositorio.listar` não cresça até
    oito parâmetros posicionais, e para que acrescentar um filtro novo não
    mude a assinatura de quem já a chama.
    """

    usuario_id: int
    status: StatusTarefa | None = None
    prioridade: PrioridadeTarefa | None = None
    prazo_ate: date | None = None
    busca: str | None = None
    ordenar_por: CampoOrdenacao = CampoOrdenacao.CRIADO_EM
    ordem: Ordem | None = None
    limite: int = 50
    deslocamento: int = 0

    @property
    def ordem_efetiva(self) -> Ordem:
        """Sentido da ordenação: o pedido, ou o natural do campo escolhido.

        `None` não quer dizer "decrescente", quer dizer "não pedi" — e o que
        se espera de "não pedi" depende do campo (ver `ordem_natural`).
        """
        return self.ordem or self.ordenar_por.ordem_natural


class TarefaRepositorio(RepositorioBase[Tarefa]):
    """Acesso aos dados de tarefa."""

    # Traduz a prioridade textual no seu peso, para que o ORDER BY siga a
    # ordem semântica (urgente primeiro) e não a alfabética. O mapa vem do
    # enum: acrescentar uma prioridade nova não exige mexer aqui.
    _ORDEM_POR_PRIORIDADE = case(
        PrioridadeTarefa.mapa_de_pesos(), value=Tarefa.prioridade, else_=99
    )

    @property
    def modelo(self) -> type[Tarefa]:
        return Tarefa

    def _coluna_de_ordenacao(self, campo: CampoOrdenacao):
        """Devolve a expressão SQL correspondente ao campo de ordenação."""
        colunas = {
            CampoOrdenacao.CRIADO_EM: Tarefa.criado_em,
            CampoOrdenacao.PRAZO: Tarefa.prazo,
            CampoOrdenacao.PRIORIDADE: self._ORDEM_POR_PRIORIDADE,
        }
        return colunas[campo]

    def _consulta(self, filtro: FiltroDeTarefas):
        """Monta o WHERE compartilhado por `listar` e `contar`.

        Os dois precisam filtrar exatamente igual: um total que não
        correspondesse à lista devolvida seria pior do que não ter total
        algum. Montar a condição em um só lugar é o que garante isso.

        Os filtros são encadeados: cada critério preenchido acrescenta uma
        condição. Nenhum critério além do usuário alcança todas as tarefas
        dele.
        """
        consulta = self._sessao.query(Tarefa).filter(
            Tarefa.usuario_id == filtro.usuario_id
        )

        if filtro.status is not None:
            consulta = consulta.filter(Tarefa.status == filtro.status.value)
        if filtro.prioridade is not None:
            consulta = consulta.filter(
                Tarefa.prioridade == filtro.prioridade.value
            )
        if filtro.prazo_ate is not None:
            consulta = consulta.filter(
                Tarefa.prazo.isnot(None), Tarefa.prazo <= filtro.prazo_ate
            )

        termo = (filtro.busca or "").strip()
        if termo:
            # `ilike` é portável: compila para `ILIKE` no PostgreSQL e para
            # `lower(a) LIKE lower(b)` no SQLite, de modo que a busca ignora
            # maiúsculas nos dois bancos.
            consulta = consulta.filter(
                Tarefa.titulo.ilike(f"%{_escapar_curingas(termo)}%", escape="\\")
            )

        return consulta

    def listar(self, filtro: FiltroDeTarefas) -> list[Tarefa]:
        """Lista as tarefas de um usuário conforme os critérios informados."""
        coluna = self._coluna_de_ordenacao(filtro.ordenar_por)
        sentido = (
            coluna.desc()
            if filtro.ordem_efetiva is Ordem.DESC
            else coluna.asc()
        )

        return (
            self._consulta(filtro)
            # Tarefa sem prazo vai para o fim nos dois sentidos. Sem isto, o
            # resultado dependeria do banco: o SQLite trata NULL como o menor
            # valor de todos, enquanto o PostgreSQL o põe no fim do crescente
            # e no início do decrescente. A mesma consulta devolveria ordens
            # diferentes em desenvolvimento e em produção.
            .order_by(nullslast(sentido))
            .offset(filtro.deslocamento)
            .limit(filtro.limite)
            .all()
        )

    def contar(self, filtro: FiltroDeTarefas) -> int:
        """Quantas tarefas atendem ao filtro, ignorando limite e deslocamento.

        É o número que permite ao cliente saber que existe mais coisa além da
        página que ele recebeu.
        """
        return self._consulta(filtro).count()
