"""Proteção de senha.

O módulo expõe um **contrato** (`HashDeSenha`) e uma implementação concreta
(`HashBcrypt`). O resto da aplicação depende apenas do contrato.

Isso não é cerimônia: o bcrypt é lento de propósito — cada hash custa
centenas de milissegundos, justamente para encarecer um ataque de força bruta.
Uma suíte de testes que cadastra dezenas de usuários pagaria esse custo em
cada um deles. Com o contrato no meio, os testes injetam uma implementação
instantânea e a aplicação continua usando o bcrypt de verdade.

A biblioteca `bcrypt` é usada **diretamente**, sem o `passlib` no meio. O
`passlib` é a escolha mais comum em tutoriais, mas a sua última versão é de
2020 e ela lê um atributo privado (`bcrypt.__about__`) que o bcrypt removeu na
versão 4.1. Quem usa as duas é obrigado a fixar `bcrypt<4.1` no
`requirements.txt` — e uma versão fixada em biblioteca de criptografia é
dívida que vence: ela impede as correções de segurança publicadas depois dela.
O `passlib` só se pagaria se o projeto precisasse migrar de algoritmo sem
invalidar as senhas já gravadas, e aqui ele não precisa.
"""

from abc import ABC, abstractmethod

import bcrypt

from app.exceptions import ValorInvalido

#: O bcrypt trunca o que passa de 72 **bytes** — não 72 caracteres. Um "ã"
#: ocupa 2 bytes em UTF-8, um emoji chega a 4: uma senha de 40 caracteres
#: acentuados pode estourar o limite. Até a versão 4.x a biblioteca cortava o
#: excedente em silêncio, o que faria duas senhas diferentes a partir do 73º
#: byte abrirem a mesma conta; a 5.0 passou a recusar. Validar aqui dá o mesmo
#: comportamento nas duas, e uma mensagem clara em vez de uma falha obscura.
LIMITE_DE_BYTES_DO_BCRYPT = 72


class HashDeSenha(ABC):
    """Contrato de quem sabe transformar e conferir senhas.

    Classe abstrata: qualquer implementação é obrigada a oferecer os dois
    métodos. Esquecer um deles gera erro na criação do objeto, e não em
    produção, na primeira tentativa de login.
    """

    @abstractmethod
    def gerar(self, senha: str) -> str:
        """Devolve o hash da senha informada."""

    @abstractmethod
    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        """Confere se a senha corresponde ao hash gravado."""


class HashBcrypt(HashDeSenha):
    """Implementação de produção, baseada no algoritmo bcrypt.

    O bcrypt gera um salt aleatório por senha: a mesma senha cadastrada por
    dois usuários produz hashes diferentes, e o hash não permite recuperar a
    senha original.

    O `custo` é o expoente do número de rodadas do algoritmo — 12 significa
    2¹² = 4096 rodadas. Cada unidade **dobra** o tempo de cálculo, e é esse
    tempo que protege o banco caso ele vaze. Baixá-lo só faz sentido em teste
    automatizado, onde o que se verifica é o comportamento, não a resistência.
    """

    def __init__(self, custo: int = 12) -> None:
        self._custo = custo

    def gerar(self, senha: str) -> str:
        em_bytes = senha.encode("utf-8")
        if len(em_bytes) > LIMITE_DE_BYTES_DO_BCRYPT:
            raise ValorInvalido(
                f"A senha ocupa {len(em_bytes)} bytes e o limite do bcrypt é "
                f"{LIMITE_DE_BYTES_DO_BCRYPT}. Caracteres acentuados contam "
                "mais de um byte cada."
            )
        return bcrypt.hashpw(em_bytes, bcrypt.gensalt(self._custo)).decode("utf-8")

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        try:
            return bcrypt.checkpw(
                senha.encode("utf-8"), hash_armazenado.encode("utf-8")
            )
        except ValueError:
            # Hash gravado em formato inválido, ou senha acima do limite de
            # bytes. Em ambos os casos a senha não corresponde — e derrubar o
            # endpoint de login com erro 500 entregaria essa informação a quem
            # está tentando adivinhar.
            return False
