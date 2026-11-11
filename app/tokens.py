"""Emissão e leitura do token de acesso.

O token é um **JWT** (JSON Web Token) assinado com HS256: um texto que carrega
dentro de si quem é o usuário e até quando vale, acompanhado de uma assinatura
feita com o segredo da aplicação. Validar não exige consulta ao banco — basta
recalcular a assinatura e conferir se ela corresponde.

Por que não guardar a sessão em uma tabela
------------------------------------------
A alternativa seria um token aleatório com uma linha em `sessoes`. Ela permite
revogar uma sessão de verdade, o que o JWT não permite: um token assinado vale
até expirar, e "sair" significa apenas o cliente descartá-lo. Em troca, cada
requisição custaria uma consulta a mais e o projeto ganharia uma tabela e uma
rotina de limpeza dos registros vencidos.

Para esta aplicação o JWT se paga: não há operação destrutiva irreversível, e a
expiração curta limita o prejuízo de um token vazado. A escolha está registrada
aqui porque é o tipo de decisão que depois ninguém lembra por que foi tomada.

Nota sobre a biblioteca
-----------------------
É usado o **PyJWT**, e não o `python-jose` que aparece em muitos tutoriais. O
PyJWT é o que a própria documentação do FastAPI passou a indicar, tem
manutenção ativa e faz só uma coisa. É o mesmo critério aplicado em
`security.py` ao preferir o `bcrypt` direto ao `passlib`.
"""

from __future__ import annotations

from datetime import timedelta

import jwt

from app.exceptions import NaoAutenticado, SessaoExpirada
from app.tempo import agora_utc

#: Algoritmo de assinatura. HS256 usa um **segredo compartilhado**: quem assina
#: e quem verifica usam a mesma chave. É o adequado aqui, onde a aplicação faz
#: as duas coisas. Algoritmos RS256 e afins existem para o caso em que um
#: serviço assina e outro apenas verifica, sem poder emitir.
ALGORITMO = "HS256"


class TokenDeAcesso:
    """Emite e lê os tokens de acesso da aplicação.

    Recebe o segredo e a validade pelo construtor em vez de lê-los do ambiente
    por conta própria. É o que permite ao teste criar uma instância com um
    segundo de validade para verificar a expiração, sem esperar uma semana nem
    alterar variável de ambiente.

    Diferente de `HashDeSenha`, não há classe abstrata aqui: a implementação
    real já é instantânea, e não existe segunda implementação plausível. Uma
    interface sem segundo implementador é cerimônia, não desenho.
    """

    def __init__(self, segredo: str, validade: timedelta) -> None:
        self._segredo = segredo
        self._validade = validade

    def emitir(self, usuario_id: int) -> str:
        """Devolve um token que identifica o usuário informado.

        As três informações gravadas são as mínimas necessárias:

        - `sub` (*subject*): quem é o usuário. Vai como texto porque é o que a
          especificação do JWT exige — versões recentes do PyJWT recusam um
          número aqui.
        - `exp` (*expiration*): até quando vale. É o único freio de um token
          vazado, já que não há como revogá-lo.
        - `iat` (*issued at*): quando foi emitido. Serve para depuração e para
          uma eventual invalidação em massa por data.

        O nome e o e-mail do usuário **não** entram. O conteúdo de um JWT é
        apenas codificado em base64, não cifrado: qualquer um que tenha o token
        lê o que há dentro. Nada que não possa ser público deve ir aqui.
        """
        agora = agora_utc()
        return jwt.encode(
            {
                "sub": str(usuario_id),
                "iat": agora,
                "exp": agora + self._validade,
            },
            self._segredo,
            algorithm=ALGORITMO,
        )

    def ler(self, token: str) -> int:
        """Devolve o id do usuário que o token identifica.

        Raises:
            SessaoExpirada: o token era válido, mas passou da validade.
            NaoAutenticado: assinatura inválida, formato corrompido ou
                conteúdo inesperado.

        As duas exceções são separadas de propósito: "sua sessão expirou, entre
        de novo" e "este token não vale nada" pedem reações diferentes do
        cliente, e as duas respondem 401.
        """
        try:
            conteudo = jwt.decode(token, self._segredo, algorithms=[ALGORITMO])
        except jwt.ExpiredSignatureError as erro:
            raise SessaoExpirada() from erro
        except jwt.InvalidTokenError as erro:
            # Família que cobre assinatura errada, base64 corrompido, algoritmo
            # não permitido e token truncado.
            raise NaoAutenticado() from erro

        sujeito = conteudo.get("sub")
        try:
            return int(sujeito)
        except (TypeError, ValueError) as erro:
            # Token assinado por esta aplicação mas sem `sub` utilizável: não
            # deveria acontecer, e tratar como não autenticado é mais seguro do
            # que deixar subir um erro 500.
            raise NaoAutenticado() from erro


def validade_a_partir_de_horas(horas: float) -> timedelta:
    """Converte a validade declarada em horas no `timedelta` correspondente."""
    return timedelta(hours=horas)
