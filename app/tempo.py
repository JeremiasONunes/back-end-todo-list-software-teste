"""Data e hora: um único momento de referência e uma coluna que preserva o fuso.

Este módulo existe por causa de uma divergência entre os dois bancos do
projeto. O PostgreSQL guarda o fuso horário de uma coluna
`DateTime(timezone=True)`; o SQLite **não** — o valor volta da consulta sem
`tzinfo`, mesmo tendo sido gravado com ele.

A consequência aparece na borda. O Pydantic serializa uma data com fuso como
`2026-01-01T10:00:00Z` e uma data sem fuso como `2026-01-01T10:00:00`. O
JavaScript do front-end lê a primeira como UTC e a segunda como horário
**local do navegador**: com o servidor em UTC e o navegador em Brasília, a
mesma tarefa chegaria três horas deslocada — e o deslocamento mudaria com o
horário de verão de quem está olhando.

Sem este módulo, o JSON de desenvolvimento (SQLite) e o de produção
(PostgreSQL) seriam diferentes. É a mesma categoria de divergência silenciosa
que o `PRAGMA foreign_keys=ON` de `database.py` evita do outro lado: o teste
passa na máquina de quem escreveu e o defeito aparece só depois do deploy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def agora_utc() -> datetime:
    """Momento atual em UTC, com o fuso declarado.

    Usada como `default` das colunas de data em vez de `datetime.now`, que
    devolve o horário local da máquina **sem** dizer qual é esse fuso — o que
    torna o valor impossível de interpretar corretamente em qualquer outro
    lugar.
    """
    return datetime.now(timezone.utc)


class DataHoraUTC(TypeDecorator):
    """Coluna de data e hora que sempre entrega UTC com fuso declarado.

    O armazenamento é feito sem fuso, em UTC, nos dois bancos — é o formato
    que SQLite e PostgreSQL tratam igual. O fuso é reatado na leitura, de modo
    que **todo** `datetime` que circula pela aplicação tem `tzinfo`, e o JSON
    da resposta termina em `Z` independentemente do banco em uso.

    Um valor sem fuso que chegue para gravação é interpretado como UTC. Isso
    mantém válidos os testes de domínio, que constroem datas fixas como
    `datetime(2026, 1, 10, 9, 0)` para verificar a RN-03 sem passar pelo banco.
    """

    impl = DateTime
    #: Permite ao SQLAlchemy reaproveitar o cache de compilação das consultas
    #: que usam este tipo. Seguro porque o tipo não tem configuração variável.
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Converte para UTC e remove o fuso antes de gravar."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Declara o fuso UTC no valor lido do banco."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
