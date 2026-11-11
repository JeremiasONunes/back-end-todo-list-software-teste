"""Exceções de domínio.

Regra de arquitetura desta aplicação: **o domínio e os serviços nunca lançam
`HTTPException`**. Eles lançam as exceções deste módulo, e a camada HTTP
(`main.py`) as traduz no código de status correspondente.

Isso tem duas consequências práticas:

1. As regras de negócio continuam válidas fora de uma API web. O mesmo
   `UsuarioServico` poderia ser usado por um programa de terminal, e nada
   nele precisaria mudar.
2. As exceções ficam organizadas em uma hierarquia. `main.py` registra um
   único tratador para `ErroDeDominio` e atende a família inteira — inclusive
   exceções que ainda não existem, desde que herdem da classe certa.
"""


class ErroDeDominio(Exception):
    """Classe base de todo erro previsto de negócio.

    A mensagem padrão fica na classe para que quem lança a exceção não precise
    repeti-la em cada `raise`, mas possa sobrescrevê-la quando houver um
    detalhe útil a acrescentar.
    """

    mensagem = "Não foi possível concluir a operação."

    def __init__(self, mensagem: str | None = None) -> None:
        self.mensagem = mensagem or type(self).mensagem
        super().__init__(self.mensagem)


# --------------------------------------------------------------------------
# Recurso inexistente — a camada HTTP traduz esta família em 404
# --------------------------------------------------------------------------

class RecursoNaoEncontrado(ErroDeDominio):
    """Pediram um registro que não existe."""

    mensagem = "Recurso não encontrado."


class UsuarioNaoEncontrado(RecursoNaoEncontrado):
    mensagem = "Usuário não encontrado."


class TarefaNaoEncontrada(RecursoNaoEncontrado):
    mensagem = "Tarefa não encontrada."


# --------------------------------------------------------------------------
# Regra de negócio violada — a camada HTTP traduz esta família em 422
# --------------------------------------------------------------------------

class RegraDeNegocioViolada(ErroDeDominio):
    """A operação é compreensível, mas contraria uma regra do negócio."""

    mensagem = "Operação recusada por uma regra de negócio."


class TituloObrigatorio(RegraDeNegocioViolada):
    mensagem = "O título da tarefa não pode ficar vazio."


class ValorInvalido(RegraDeNegocioViolada):
    """Valor fora do conjunto aceito por um campo do domínio."""

    mensagem = "Valor inválido para o campo."


# --------------------------------------------------------------------------
# Conflito e autorização — traduzidos em 409, 401 e 403
# --------------------------------------------------------------------------

class EmailJaCadastrado(ErroDeDominio):
    """RN-01: um e-mail não pode ser usado por dois usuários."""

    mensagem = "E-mail já cadastrado."


class CredenciaisInvalidas(ErroDeDominio):
    """E-mail inexistente ou senha incorreta.

    A mensagem é deliberadamente a mesma nos dois casos: dizer que o e-mail
    não existe revelaria a um atacante quais endereços estão cadastrados.
    """

    mensagem = "E-mail ou senha inválidos."


class NaoAutenticado(ErroDeDominio):
    """Requisição sem token, ou com um token que não vale nada.

    Cobre o cabeçalho `Authorization` ausente, mal formado, assinado com outro
    segredo ou corrompido. A mensagem é a mesma em todos os casos: detalhar
    *por que* o token foi recusado ajuda mais quem está tentando forjar um do
    que quem está integrando de boa-fé — e para este, a documentação serve
    melhor que a mensagem de erro.
    """

    mensagem = "É necessário autenticar-se para acessar este recurso."


class SessaoExpirada(NaoAutenticado):
    """O token era legítimo, mas passou da validade.

    Herda de `NaoAutenticado` porque responde o mesmo 401. Existe separada
    porque pede outra reação do cliente: aqui faz sentido pedir a senha de
    novo, enquanto um token inválido costuma indicar defeito de integração.
    """

    mensagem = "Sua sessão expirou. Entre novamente."


class AcessoNaoAutorizado(ErroDeDominio):
    """Tentativa de mexer em uma tarefa que pertence a outro usuário."""

    mensagem = "Esta tarefa pertence a outro usuário."
