"""Tradução das mensagens de validação do Pydantic para português.

O Pydantic descreve um campo recusado em inglês: `String should have at least
1 character`. Os erros de negócio desta API já respondem em português, e os
formulários do front-end exibem a mensagem recebida diretamente na tela. Sem
esta tradução, a mesma tela mostraria português quando a regra é de negócio e
inglês quando a regra é de formato.

A tabela cobre os tipos de erro que os campos desta API podem produzir, e não
o catálogo inteiro do Pydantic. O que não estiver mapeado cai na mensagem
original — é melhor uma frase em inglês do que uma genérica que não diz qual é
o problema.
"""

from __future__ import annotations

from typing import Any

#: Nome público de cada campo, como o cliente o envia. O `loc` do erro traz o
#: nome em `snake_case` quando a validação falha antes da conversão de alias.
NOMES_PUBLICOS = {
    "usuario_id": "usuarioId",
    "prazo_ate": "prazoAte",
    "ordenar_por": "ordenarPor",
}


def _lista_de_valores(contexto: dict[str, Any]) -> str:
    """Formata os valores aceitos por um enum, como o Pydantic os entrega."""
    esperados = contexto.get("expected", "")
    return str(esperados).replace("'", "").replace(" or ", " ou ")


#: Cada entrada recebe o contexto do erro (`ctx`) e devolve a frase em
#: português. O contexto traz os limites declarados no schema — `min_length`,
#: `ge`, `expected`... — o que permite citar o número exato em vez de uma
#: mensagem vaga.
TRADUCOES = {
    "missing": lambda _: "campo obrigatório.",
    "string_type": lambda _: "deve ser um texto.",
    "int_type": lambda _: "deve ser um número inteiro.",
    "int_parsing": lambda _: "deve ser um número inteiro.",
    "bool_parsing": lambda _: "deve ser verdadeiro ou falso.",
    "json_invalid": lambda _: "o corpo da requisição não é um JSON válido.",
    "string_too_short": lambda ctx: (
        f"deve ter no mínimo {ctx.get('min_length')} caracteres."
    ),
    "string_too_long": lambda ctx: (
        f"deve ter no máximo {ctx.get('max_length')} caracteres."
    ),
    "greater_than_equal": lambda ctx: f"deve ser maior ou igual a {ctx.get('ge')}.",
    "less_than_equal": lambda ctx: f"deve ser menor ou igual a {ctx.get('le')}.",
    "greater_than": lambda ctx: f"deve ser maior que {ctx.get('gt')}.",
    "less_than": lambda ctx: f"deve ser menor que {ctx.get('lt')}.",
    "enum": lambda ctx: f"valor inválido. Aceitos: {_lista_de_valores(ctx)}.",
    "date_parsing": lambda _: "deve ser uma data no formato AAAA-MM-DD.",
    "date_type": lambda _: "deve ser uma data no formato AAAA-MM-DD.",
    "date_from_datetime_parsing": lambda _: (
        "deve ser uma data no formato AAAA-MM-DD."
    ),
    "datetime_parsing": lambda _: "deve ser uma data e hora no formato ISO 8601.",
}


def nome_do_campo(localizacao: tuple[Any, ...]) -> str:
    """Caminho até o campo recusado, com o nome que o cliente usa.

    O `loc` do Pydantic começa pela parte da requisição — `("body", "titulo")`,
    `("query", "status")` — e essa primeira posição não interessa a quem
    preencheu o formulário.
    """
    partes = [str(parte) for parte in localizacao[1:]]
    if not partes:
        return ""
    partes[-1] = NOMES_PUBLICOS.get(partes[-1], partes[-1])
    return ".".join(partes)


def traduzir(erro: dict[str, Any]) -> str:
    """Devolve a frase em português para um erro de validação do Pydantic.

    O caso do e-mail é tratado em separado porque o Pydantic o classifica como
    `value_error` genérico, mesmo tipo usado por validadores próprios — não há
    como distingui-los pelo tipo, só pela mensagem.
    """
    tipo = erro.get("type", "")
    contexto = erro.get("ctx") or {}
    mensagem_original = erro.get("msg", "")

    if tipo == "value_error" and "email" in mensagem_original.lower():
        return "e-mail inválido."

    traducao = TRADUCOES.get(tipo)
    return traducao(contexto) if traducao else mensagem_original


def descrever(erros: list[dict[str, Any]]) -> str:
    """Resume todos os erros de uma requisição em uma única frase.

    Mantém um item por campo recusado, separados por ` | `, em vez de informar
    apenas o primeiro: quem preencheu um formulário com três campos errados
    deve poder corrigir os três de uma vez.
    """
    partes = []
    for erro in erros:
        campo = nome_do_campo(erro.get("loc", ()))
        frase = traduzir(erro)
        partes.append(f"{campo}: {frase}" if campo else frase)

    return " | ".join(partes) or "Requisição inválida."
