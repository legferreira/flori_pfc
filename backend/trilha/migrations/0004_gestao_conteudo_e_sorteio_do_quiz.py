import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def copiar_fontes_dos_cards(apps, schema_editor):
    Card = apps.get_model('trilha', 'Card')
    FonteCard = apps.get_model('trilha', 'FonteCard')
    for card in Card.objects.prefetch_related('fontes'):
        FonteCard.objects.bulk_create(
            FonteCard(card=card, nome=fonte.nome[:120], url=fonte.url, ordem=ordem)
            for ordem, fonte in enumerate(sorted(card.fontes.all(), key=lambda f: f.nome), start=1)
        )


def preencher_codigos_e_passos(apps, schema_editor):
    Assunto = apps.get_model('trilha', 'Assunto')
    GuiaRapido = apps.get_model('trilha', 'GuiaRapido')
    for assunto in Assunto.objects.prefetch_related('cards'):
        prefixos = {card.codigo.split('.')[0] for card in assunto.cards.all() if '.' in card.codigo}
        if len(prefixos) == 1:
            codigo = f'A{prefixos.pop()}'
            if not Assunto.objects.filter(codigo=codigo).exists():
                assunto.codigo = codigo
                assunto.save(update_fields=['codigo'])

    guias = list(GuiaRapido.objects.order_by('titulo'))
    for ordem, guia in enumerate(guias, start=1):
        guia.ordem = ordem
        guia.passos = [
            f"{p.get('titulo', '')} {p.get('descricao', '')}".strip() if isinstance(p, dict) else str(p)
            for p in guia.passos
        ]
        if guia.titulo == 'Menstruei, e agora?' or len(guias) == 1:
            if not GuiaRapido.objects.filter(codigo='G1').exists():
                guia.codigo = 'G1'
        guia.save(update_fields=['ordem', 'passos', 'codigo'])


def finalizar_tentativas_antigas(apps, schema_editor):
    TentativaQuiz = apps.get_model('trilha', 'TentativaQuiz')
    for tentativa in TentativaQuiz.objects.filter(finalizada_em__isnull=True):
        tentativa.finalizada_em = tentativa.criado_em
        tentativa.save(update_fields=['finalizada_em'])


def preencher_conclusao_da_trilha(apps, schema_editor):
    Trilha = apps.get_model('trilha', 'Trilha')
    Card = apps.get_model('trilha', 'Card')
    ProgressoCard = apps.get_model('trilha', 'ProgressoCard')
    ProgressoTrilha = apps.get_model('trilha', 'ProgressoTrilha')
    TentativaQuiz = apps.get_model('trilha', 'TentativaQuiz')
    for trilha in Trilha.objects.all():
        visiveis = set(
            Card.objects.filter(ativo=True, assunto__ativo=True, assunto__trilha=trilha).values_list('id', flat=True)
        )
        feitos = {}
        ultima = {}
        for usuario_id, card_id, concluido_em in ProgressoCard.objects.filter(card__assunto__trilha=trilha).values_list(
            'usuario_id', 'card_id', 'concluido_em',
        ):
            feitos.setdefault(usuario_id, set()).add(card_id)
            if usuario_id not in ultima or concluido_em > ultima[usuario_id]:
                ultima[usuario_id] = concluido_em
        primeira_tentativa = {}
        for usuario_id, criado_em in TentativaQuiz.objects.filter(trilha=trilha).values_list('usuario_id', 'criado_em'):
            if usuario_id not in primeira_tentativa or criado_em < primeira_tentativa[usuario_id]:
                primeira_tentativa[usuario_id] = criado_em
        concluiram = {u for u, cards in feitos.items() if visiveis and visiveis <= cards} | set(primeira_tentativa)
        for usuario_id in concluiram:
            ProgressoTrilha.objects.get_or_create(
                usuario_id=usuario_id, trilha=trilha,
                defaults={'trilha_concluida_em': ultima.get(usuario_id) or primeira_tentativa[usuario_id]},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('trilha', '0003_conteudo_ativo'),
        ('users', '0011_log_documentos_aceitos'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='assunto', name='assunto_ordem_unica_por_trilha'),
        migrations.RemoveConstraint(model_name='card', name='card_ordem_unica_por_assunto'),
        migrations.RemoveConstraint(model_name='pergunta', name='pergunta_ordem_unica_por_trilha'),
        migrations.AddField(
            model_name='assunto', name='codigo',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='assunto', name='descricao', field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(model_name='assunto', name='excluido_em', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='assunto', name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False,
        ),
        migrations.AddField(model_name='card', name='excluido_em', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='card', name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False,
        ),
        migrations.AddField(
            model_name='guiarapido', name='codigo',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AddField(model_name='guiarapido', name='ordem', field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name='guiarapido', name='excluido_em', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='guiarapido', name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False,
        ),
        migrations.AlterField(
            model_name='guiarapido', name='introducao', field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='guiarapido', name='fontes',
            field=models.ManyToManyField(blank=True, related_name='guias_rapidos', to='trilha.fonte'),
        ),
        migrations.AlterModelOptions(name='guiarapido', options={'ordering': ['ordem']}),
        migrations.AddField(model_name='pergunta', name='excluido_em', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='pergunta', name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now), preserve_default=False,
        ),
        migrations.AlterField(
            model_name='pergunta', name='assunto',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='perguntas',
                to='trilha.assunto',
            ),
        ),
        migrations.CreateModel(
            name='FonteCard',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=120)),
                ('url', models.URLField(max_length=300)),
                ('ordem', models.PositiveSmallIntegerField()),
                ('card', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='fontes_copiadas', to='trilha.card',
                )),
            ],
            options={'db_table': 'trilha_fontes_card', 'ordering': ['ordem']},
        ),
        migrations.RunPython(copiar_fontes_dos_cards, migrations.RunPython.noop),
        migrations.RemoveField(model_name='card', name='fontes'),
        migrations.AlterField(
            model_name='fontecard', name='card',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fontes', to='trilha.card'),
        ),
        migrations.RunPython(preencher_codigos_e_passos, migrations.RunPython.noop),
        migrations.RenameField(model_name='tentativaquiz', old_name='total', new_name='total_perguntas'),
        migrations.AlterField(
            model_name='tentativaquiz', name='acertos', field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='tentativaquiz', name='percentual', field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='tentativaquiz', name='aprovada', field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tentativaquiz', name='finalizada_em', field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(finalizar_tentativas_antigas, migrations.RunPython.noop),
        migrations.CreateModel(
            name='TentativaPergunta',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ordem', models.PositiveSmallIntegerField()),
                ('acertou', models.BooleanField(blank=True, null=True)),
                ('opcao_escolhida', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                    to='trilha.opcao',
                )),
                ('pergunta', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='respostas', to='trilha.pergunta',
                )),
                ('tentativa', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='perguntas', to='trilha.tentativaquiz',
                )),
            ],
            options={
                'db_table': 'trilha_tentativas_perguntas',
                'ordering': ['ordem'],
                'constraints': [
                    models.UniqueConstraint(fields=('tentativa', 'pergunta'), name='pergunta_unica_por_tentativa'),
                    models.UniqueConstraint(fields=('tentativa', 'ordem'), name='ordem_unica_por_tentativa'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ProgressoTrilha',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('trilha_concluida_em', models.DateTimeField(blank=True, null=True)),
                ('trilha', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='conclusoes', to='trilha.trilha',
                )),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='conclusoes_trilha', to='users.usuario',
                )),
            ],
            options={
                'db_table': 'trilha_progresso_trilha',
                'constraints': [
                    models.UniqueConstraint(fields=('usuario', 'trilha'), name='progresso_trilha_unico_por_usuaria'),
                ],
            },
        ),
        migrations.RunPython(preencher_conclusao_da_trilha, migrations.RunPython.noop),
    ]
