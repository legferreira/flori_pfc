from getpass import getpass
import os

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from users.auditoria import registrar_log_admin
from users.models import Consentimento, LogAtividade, Usuario
from users.services import VERSAO_POLITICA_PRIVACIDADE, VERSAO_TERMOS_USO

DATA_NASCIMENTO_ADMIN = '01/01/1990'
TAMANHO_MINIMO_SENHA_ADMIN = 12


class Command(BaseCommand):
    help = 'Cria ou promove a conta admin. Lê ADMIN_EMAIL, ADMIN_NOME e ADMIN_SENHA do ambiente ou pergunta.'

    def handle(self, *args, **options):
        email = (os.getenv('ADMIN_EMAIL') or input('Email do admin: ')).strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError('Email inválido.')

        usuario = Usuario.objects.filter(email=email).first()
        precisa_senha = usuario is None or not usuario.tem_senha()
        nome = ''
        if usuario is None:
            nome = (os.getenv('ADMIN_NOME') or input('Nome do admin: ')).strip()
            if not nome:
                raise CommandError('Nome é obrigatório.')
        senha = self._senha() if precisa_senha else None

        with transaction.atomic():
            criado = usuario is None
            if criado:
                usuario = self._criar(email, nome)
            if senha:
                usuario.definir_senha(senha)
            usuario.perfil = Usuario.Perfil.ADMIN
            usuario.save()
            self._garantir_consentimentos(usuario)
            registrar_log_admin(
                usuario, LogAtividade.Acao.ADMIN_CRIADO, 'usuario', usuario.id,
                {'origem': 'criar_admin', 'conta_nova': criado},
            )

        situacao = 'criado' if criado else 'promovido ou confirmado'
        self.stdout.write(self.style.SUCCESS(f'Admin {situacao}: {usuario.apelido}.'))

    def _senha(self):
        senha = os.getenv('ADMIN_SENHA') or ''
        if not senha:
            senha = getpass('Senha do admin: ')
            if senha != getpass('Repita a senha: '):
                raise CommandError('As senhas não conferem.')
        if len(senha) < TAMANHO_MINIMO_SENHA_ADMIN:
            raise CommandError(f'A senha do admin precisa ter pelo menos {TAMANHO_MINIMO_SENHA_ADMIN} caracteres.')
        return senha

    def _criar(self, email, nome_completo):
        nome, _, sobrenome = nome_completo.partition(' ')
        return Usuario(
            nome=nome[:100],
            sobrenome=(sobrenome.strip() or 'Admin')[:100],
            apelido=nome[:50],
            data_nascimento=DATA_NASCIMENTO_ADMIN,
            email=email,
        )

    def _garantir_consentimentos(self, usuario):
        atuais = usuario.consentimentos_atuais()
        for tipo, versao in (
            (Consentimento.Tipo.TERMOS_USO, VERSAO_TERMOS_USO),
            (Consentimento.Tipo.POLITICA_PRIVACIDADE, VERSAO_POLITICA_PRIVACIDADE),
        ):
            atual = atuais.get(tipo)
            if atual is None or not atual.aceito:
                Consentimento.objects.create(usuario=usuario, tipo=tipo, versao_documento=versao, aceito=True)
