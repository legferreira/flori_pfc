from datetime import timedelta
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from trilha.models import Certificado, ProgressoCard, ProgressoTrilha, TentativaQuiz, Trilha
from trilha.services import ALFABETO_CODIGO, aprovado, cards_visiveis, percentual, perguntas_visiveis
from users.models import Consentimento, LogAtividade, Usuario
from users.services import VERSAO_POLITICA_PRIVACIDADE, VERSAO_TERMOS_USO

DOMINIO_DEMO = '@demo.flori.test'
NOMES = [
    'Ana', 'Bia', 'Carla', 'Duda', 'Elisa', 'Fernanda', 'Gabi', 'Helena', 'Isa', 'Julia',
    'Karen', 'Lara', 'Malu', 'Nina', 'Olivia', 'Paula', 'Quezia', 'Rita', 'Sofia', 'Tati',
    'Ursula', 'Vivi', 'Wanda', 'Xenia', 'Yasmin', 'Zoe', 'Alice', 'Bruna', 'Clara', 'Diana',
]


def exigir_debug(options):
    if not settings.DEBUG and not options['forcar']:
        raise CommandError('DEBUG está desligado. Use --forcar se tiver certeza.')


class Command(BaseCommand):
    help = 'Cria users fictícios de demonstração (email terminando em @demo.flori.test) para o dashboard admin.'

    def add_arguments(self, parser):
        parser.add_argument('--quantidade', type=int, default=30)
        parser.add_argument('--forcar', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        exigir_debug(options)
        trilha = Trilha.objects.filter(ativa=True).first()
        if trilha is None:
            raise CommandError('Rode carregar_trilha antes de popular a demonstração.')

        sorteio = random.Random(42)
        cards = list(cards_visiveis(trilha).order_by('assunto__ordem', 'ordem'))
        agora = timezone.now()
        criados = 0
        for i in range(options['quantidade']):
            email = f'demo{i + 1:02d}{DOMINIO_DEMO}'
            if Usuario.objects.filter(email=email).exists():
                continue
            nome = NOMES[i % len(NOMES)]
            usuario = Usuario(
                nome=nome, sobrenome='Demonstração', apelido=nome,
                data_nascimento=f'{sorteio.randint(1, 28):02d}/{sorteio.randint(1, 12):02d}/{sorteio.randint(2000, 2011)}',
                email=email, demo=True,
            )
            usuario.definir_sem_senha()
            usuario.save()
            cadastro = agora - timedelta(days=sorteio.randint(0, 330), hours=sorteio.randint(0, 23))
            Usuario.objects.filter(pk=usuario.pk).update(criado_em=cadastro)
            self._consentimentos(usuario, sorteio)
            self._progresso(usuario, trilha, cards, sorteio, cadastro, agora)
            self._acessos(usuario, sorteio, cadastro, agora)
            criados += 1

        self.stdout.write(self.style.SUCCESS(f'{criados} users de demonstração criados.'))

    def _consentimentos(self, usuario, sorteio):
        for tipo, versao in (
            (Consentimento.Tipo.TERMOS_USO, VERSAO_TERMOS_USO),
            (Consentimento.Tipo.POLITICA_PRIVACIDADE, VERSAO_POLITICA_PRIVACIDADE),
        ):
            Consentimento.objects.create(usuario=usuario, tipo=tipo, versao_documento=versao, aceito=True)
        if sorteio.random() < 0.1:
            Consentimento.objects.create(
                usuario=usuario, tipo=Consentimento.Tipo.POLITICA_PRIVACIDADE,
                versao_documento=VERSAO_POLITICA_PRIVACIDADE, aceito=False,
            )

    def _progresso(self, usuario, trilha, cards, sorteio, cadastro, agora):
        feitos = cards[:sorteio.choice([0, 0, 1, 2, 3, 4, 6, 8, 10, 12, 12, 12])]
        momentos = []
        for card in feitos:
            momentos.append(cadastro + (agora - cadastro) * sorteio.random())
            ProgressoCard.objects.create(usuario=usuario, card=card, concluido_em=momentos[-1])
        if not cards or len(feitos) < len(cards):
            return
        ProgressoTrilha.objects.create(usuario=usuario, trilha=trilha, trilha_concluida_em=max(momentos))
        total = min(10, perguntas_visiveis(trilha).count()) or 10
        for _ in range(sorteio.randint(1, 3)):
            acertos = sorteio.randint(total // 2, total)
            aprovada = aprovado(acertos, total)
            tentativa = TentativaQuiz.objects.create(
                usuario=usuario, trilha=trilha, acertos=acertos, total_perguntas=total,
                percentual=percentual(acertos, total), aprovada=aprovada, finalizada_em=agora,
            )
            if aprovada and not Certificado.objects.filter(usuario=usuario, trilha=trilha).exists():
                letras = ''.join(sorteio.choice(ALFABETO_CODIGO) for _ in range(8))
                Certificado.objects.create(
                    usuario=usuario, trilha=trilha, tentativa=tentativa,
                    codigo=f'DEMO-{letras[:4]}-{letras[4:]}',
                    nome_completo=f'{usuario.nome} {usuario.sobrenome}',
                )
                break

    def _acessos(self, usuario, sorteio, cadastro, agora):
        for _ in range(sorteio.randint(0, 4)):
            quando = cadastro + (agora - cadastro) * sorteio.random()
            LogAtividade.objects.create(usuario=usuario, acao=LogAtividade.Acao.LOGIN_GOOGLE, criado_em=quando)
