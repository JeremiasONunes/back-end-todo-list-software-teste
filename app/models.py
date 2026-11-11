"""Modelos de domínio: as entidades do sistema, com seus dados e suas regras.

Antes desta refatoração, estas classes eram apenas listas de colunas — o que
se chama de *modelo anêmico*: dado sem comportamento. As regras de negócio
viviam dentro das funções de rota, de modo que a mesma regra podia ser
reescrita de forma diferente em cada endpoint que a tocasse.

Agora cada entidade é responsável por manter o próprio estado válido. A regra
RN-03, por exemplo, não está em nenhuma rota: ela está nos métodos `concluir`
e `reabrir` da `Tarefa`, que são o único caminho possível para mudar o status.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates

from app.database import Base
from app.enums import PrioridadeTarefa, StatusTarefa
from app.exceptions import TituloObrigatorio, ValorInvalido
from app.security import HashDeSenha
from app.tempo import DataHoraUTC, agora_utc


class Usuario(Base):
    """Usuário do sistema, dono de um conjunto de tarefas."""

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(180), nullable=False, unique=True, index=True)
    # O hash é privado: nenhuma camada acima precisa — nem deve — ler este
    # valor. Quem quiser conferir uma senha usa `senha_confere`.
    _senha_hash = Column("senha_hash", String(255), nullable=False)
    criado_em = Column(DataHoraUTC, nullable=False, default=agora_utc)

    tarefas = relationship(
        "Tarefa",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __init__(self, *, nome: str, email: str) -> None:
        """Cria um usuário ainda sem senha definida.

        A senha não entra pelo construtor de propósito: ela só pode ser
        gravada por `definir_senha`, que é o método que garante o hash.

        O `*` obriga a chamada a nomear os argumentos. `Usuario("Ana",
        "ana@exemplo.com")` passa a ser erro — e com ele desaparece a chance
        de trocar nome por e-mail sem ninguém perceber, já que os dois são
        texto e nenhuma verificação de tipo pegaria a troca.
        """
        self.nome = nome
        self.email = self.normalizar_email(email)

    @staticmethod
    def normalizar_email(email: str) -> str:
        """Padroniza o e-mail antes de gravar ou comparar.

        `"  ANA@Exemplo.com "` e `"ana@exemplo.com"` são o mesmo endereço. Sem
        esta normalização, a RN-01 deixaria passar duplicatas que diferem
        apenas em espaços ou maiúsculas.

        É `staticmethod` porque a regra não depende de nenhum usuário em
        particular: o serviço de cadastro vai chamá-la na *consulta* que
        procura um e-mail já existente, antes de haver objeto algum.
        """
        return email.strip().lower()

    def definir_senha(self, senha: str, hasher: HashDeSenha) -> None:
        """Grava a senha em forma de hash (RN-05).

        O texto puro é usado e descartado aqui dentro; nunca é atribuído a um
        atributo do objeto nem chega ao banco.

        O `hasher` entra como argumento em vez de ser criado aqui dentro: é o
        que permite ao teste injetar uma implementação instantânea e à
        aplicação usar o bcrypt de verdade, sem que esta classe conheça
        nenhuma das duas.
        """
        self._senha_hash = hasher.gerar(senha)

    def senha_confere(self, senha: str, hasher: HashDeSenha) -> bool:
        """Informa se a senha apresentada corresponde à cadastrada."""
        return hasher.verificar(senha, self._senha_hash)

    @property
    def senha_hash(self) -> str:
        """Hash da senha, para conferência durante a depuração."""
        return self._senha_hash

    def tarefas_pendentes(self) -> list[Tarefa]:
        """Tarefas do usuário que ainda não foram concluídas.

        Este método existe graças à agregação declarada em `tarefas`: o
        usuário conhece as suas tarefas e sabe responder sobre elas.
        """
        return [
            tarefa
            for tarefa in self.tarefas
            if tarefa.status is StatusTarefa.PENDENTE
        ]

    @validates("nome")
    def _validar_nome(self, _campo: str, valor: str) -> str:
        """Roda a cada atribuição a `nome`, inclusive no construtor.

        É isso que torna a regra inescapável: ela não vale só na criação, mas
        também em `usuario.nome = "  "` feito em qualquer lugar do sistema.
        """
        if not valor or not valor.strip():
            raise ValorInvalido("O nome do usuário não pode ficar vazio.")
        return valor.strip()

    def __repr__(self) -> str:
        """Representação legível para depuração e mensagens de teste.

        Sem a senha e sem o hash, propositalmente: um `print` de objeto não
        deve despejar credencial em log algum.
        """
        return f"<Usuario id={self.id} email={self.email!r}>"


class Tarefa(Base):
    """Tarefa pertencente a um usuário."""

    __tablename__ = "tarefas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    titulo = Column(String(200), nullable=False)
    # Status e data de conclusão são privados porque estão amarrados entre si
    # pela RN-03: mexer em um sem o outro deixaria a tarefa em estado
    # inconsistente. Só `concluir` e `reabrir` podem alterá-los.
    _status = Column("status", String(20), nullable=False)
    prioridade = Column(String(20), nullable=False)
    prazo = Column(Date, nullable=True)
    criado_em = Column(DataHoraUTC, nullable=False, default=agora_utc)
    atualizado_em = Column(
        DataHoraUTC, nullable=False, default=agora_utc, onupdate=agora_utc
    )
    _concluido_em = Column("concluido_em", DataHoraUTC, nullable=True)

    usuario = relationship("Usuario", back_populates="tarefas")

    def __init__(
        self,
        *,
        usuario_id: int,
        titulo: str,
        prioridade: PrioridadeTarefa | str = PrioridadeTarefa.MEDIA,
        prazo: date | None = None,
    ) -> None:
        """Cria uma tarefa sempre pendente e sem data de conclusão (RN-02).

        Não existe forma de criar uma tarefa já concluída: o status inicial não
        é parâmetro. Esta é a RN-02 garantida por construção, e não por
        disciplina de quem chama.
        """
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.prioridade = prioridade
        self.prazo = prazo
        self._status = StatusTarefa.PENDENTE.value
        self._concluido_em = None

    # ---------------------------------------------------------------- leitura

    @hybrid_property
    def status(self) -> StatusTarefa:
        """Status atual, como membro do enum. Somente leitura.

        Não há setter: `tarefa.status = "concluida"` levanta `AttributeError`.
        Para mudar o status existem `concluir` e `reabrir`, que cuidam também
        da data de conclusão.
        """
        return StatusTarefa(self._status)

    @status.expression
    def status(cls):  # noqa: N805 - assinatura exigida pelo SQLAlchemy
        """Versão da propriedade usada dentro de consultas SQL.

        Permite escrever `filter(Tarefa.status == StatusTarefa.PENDENTE)` no
        repositório, mesmo com a coluna sendo privada.
        """
        return cls._status

    @property
    def concluido_em(self) -> datetime | None:
        """Momento da conclusão, ou `None` se a tarefa está pendente.

        Somente leitura: quem define este valor é a própria tarefa, ao ser
        concluída.
        """
        return self._concluido_em

    # -------------------------------------------------------------- operações

    def concluir(self, agora: datetime | None = None) -> None:
        """Conclui a tarefa e registra o momento (RN-03).

        Concluir uma tarefa já concluída não faz nada — em particular, **não**
        sobrescreve a data original. É esse caso que impede que editar o título
        de uma tarefa antiga falsifique a sua data de conclusão.
        """
        self._status = StatusTarefa.CONCLUIDA.value
        self._concluido_em = agora or agora_utc()

    def reabrir(self) -> None:
        """Devolve a tarefa para pendente e apaga a data de conclusão (RN-03)."""
        if self.status is StatusTarefa.PENDENTE:
            return
        self._status = StatusTarefa.PENDENTE.value
        self._concluido_em = None

    def definir_status(
        self, novo_status: StatusTarefa | str, agora: datetime | None = None
    ) -> None:
        """Aplica o status informado pela operação correspondente.

        Existe para atender ao `PATCH`, que recebe o status como um campo
        qualquer, sem saber que por trás dele há duas operações distintas.
        """
        status = StatusTarefa(novo_status)
        if status is StatusTarefa.CONCLUIDA:
            self.concluir(agora)
        else:
            self.reabrir()

    def esta_atrasada(self, hoje: date | None = None) -> bool:
        """Informa se o prazo venceu com a tarefa ainda pendente.

        Tarefa sem prazo nunca está atrasada; tarefa concluída também não,
        mesmo que tenha sido concluída depois do prazo.
        """
        if self.prazo is None or self.status is StatusTarefa.CONCLUIDA:
            return False
        return self.prazo < (hoje or date.today())

    def pertence_a(self, usuario_id: int) -> bool:
        """Informa se a tarefa é de um determinado usuário."""
        return self.usuario_id == usuario_id

    # -------------------------------------------------------------- validação

    @validates("titulo")
    def _validar_titulo(self, _campo: str, valor: str) -> str:
        """Recusa título vazio, aqui e em qualquer ponto do programa."""
        if valor is None or not valor.strip():
            raise TituloObrigatorio()
        return valor.strip()

    @validates("prioridade")
    def _validar_prioridade(self, _campo: str, valor: object) -> str:
        """Aceita o enum ou o texto correspondente, e grava sempre o texto."""
        try:
            return PrioridadeTarefa(valor).value
        except ValueError as erro:
            permitidos = ", ".join(p.value for p in PrioridadeTarefa)
            raise ValorInvalido(
                f"Prioridade inválida. Valores aceitos: {permitidos}."
            ) from erro

    def __repr__(self) -> str:
        return (
            f"<Tarefa id={self.id} titulo={self.titulo!r} "
            f"status={self._status!r}>"
        )
