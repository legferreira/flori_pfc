import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("users", "0008_alter_usuario_apelido"),
    ]

    operations = [
        migrations.CreateModel(
            name="Assunto",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("titulo", models.CharField(max_length=100)),
                ("descricao", models.CharField(max_length=200)),
                (
                    "cor",
                    models.CharField(
                        help_text="Cor da marca em hexadecimal, ex: #EDBFD8",
                        max_length=7,
                    ),
                ),
                ("ordem", models.PositiveSmallIntegerField()),
            ],
            options={
                "db_table": "trilha_assuntos",
                "ordering": ["ordem"],
            },
        ),
        migrations.CreateModel(
            name="Fonte",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("nome", models.CharField(max_length=200)),
                ("url", models.URLField(max_length=500, unique=True)),
            ],
            options={
                "db_table": "trilha_fontes",
            },
        ),
        migrations.CreateModel(
            name="Trilha",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("nome", models.CharField(max_length=120)),
                ("carga_horaria_minutos", models.PositiveSmallIntegerField(default=60)),
                (
                    "nota_minima_percentual",
                    models.PositiveSmallIntegerField(default=70),
                ),
                ("ativa", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "trilhas",
            },
        ),
        migrations.CreateModel(
            name="Card",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("codigo", models.CharField(max_length=10, unique=True)),
                ("tema", models.CharField(max_length=100)),
                ("explicacao", models.TextField()),
                ("exemplo", models.CharField(blank=True, max_length=255)),
                ("secoes", models.JSONField(blank=True, default=list)),
                ("cta", models.CharField(blank=True, max_length=255)),
                ("ordem", models.PositiveSmallIntegerField()),
                (
                    "assunto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cards",
                        to="trilha.assunto",
                    ),
                ),
                (
                    "fontes",
                    models.ManyToManyField(related_name="cards", to="trilha.fonte"),
                ),
            ],
            options={
                "db_table": "trilha_cards",
                "ordering": ["ordem"],
            },
        ),
        migrations.CreateModel(
            name="GuiaRapido",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("titulo", models.CharField(max_length=100)),
                ("introducao", models.CharField(max_length=255)),
                ("passos", models.JSONField(default=list)),
                ("ativo", models.BooleanField(default=True)),
                (
                    "fontes",
                    models.ManyToManyField(
                        related_name="guias_rapidos", to="trilha.fonte"
                    ),
                ),
            ],
            options={
                "db_table": "trilha_guias_rapidos",
            },
        ),
        migrations.CreateModel(
            name="Pergunta",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("codigo", models.CharField(max_length=10, unique=True)),
                ("enunciado", models.CharField(max_length=255)),
                ("ordem", models.PositiveSmallIntegerField()),
                (
                    "assunto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perguntas",
                        to="trilha.assunto",
                    ),
                ),
                (
                    "trilha",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="perguntas",
                        to="trilha.trilha",
                    ),
                ),
            ],
            options={
                "db_table": "trilha_perguntas",
                "ordering": ["ordem"],
            },
        ),
        migrations.CreateModel(
            name="Opcao",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("texto", models.CharField(max_length=200)),
                ("correta", models.BooleanField(default=False)),
                ("ordem", models.PositiveSmallIntegerField()),
                (
                    "pergunta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opcoes",
                        to="trilha.pergunta",
                    ),
                ),
            ],
            options={
                "db_table": "trilha_opcoes",
                "ordering": ["ordem"],
            },
        ),
        migrations.CreateModel(
            name="ProgressoCard",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "concluido_em",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "card",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progressos",
                        to="trilha.card",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progresso_trilha",
                        to="users.usuario",
                    ),
                ),
            ],
            options={
                "db_table": "trilha_progresso",
            },
        ),
        migrations.CreateModel(
            name="TentativaQuiz",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("acertos", models.PositiveSmallIntegerField()),
                ("total", models.PositiveSmallIntegerField()),
                ("percentual", models.PositiveSmallIntegerField()),
                ("aprovada", models.BooleanField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tentativas_quiz",
                        to="users.usuario",
                    ),
                ),
                (
                    "trilha",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tentativas",
                        to="trilha.trilha",
                    ),
                ),
            ],
            options={
                "db_table": "trilha_tentativas_quiz",
            },
        ),
        migrations.CreateModel(
            name="Certificado",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("codigo", models.CharField(max_length=20, unique=True)),
                ("nome_completo", models.CharField(max_length=205)),
                ("emitido_em", models.DateTimeField(auto_now_add=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificados",
                        to="users.usuario",
                    ),
                ),
                (
                    "tentativa",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="certificado",
                        to="trilha.tentativaquiz",
                    ),
                ),
                (
                    "trilha",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="certificados",
                        to="trilha.trilha",
                    ),
                ),
            ],
            options={
                "db_table": "trilha_certificados",
            },
        ),
        migrations.AddField(
            model_name="assunto",
            name="trilha",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assuntos",
                to="trilha.trilha",
            ),
        ),
        migrations.AddConstraint(
            model_name="card",
            constraint=models.UniqueConstraint(
                fields=("assunto", "ordem"), name="card_ordem_unica_por_assunto"
            ),
        ),
        migrations.AddConstraint(
            model_name="progressocard",
            constraint=models.UniqueConstraint(
                fields=("usuario", "card"), name="progresso_unico_por_usuaria_e_card"
            ),
        ),
        migrations.AddIndex(
            model_name="tentativaquiz",
            index=models.Index(
                fields=["usuario", "trilha", "-criado_em"],
                name="trilha_tent_usuario_ed13a4_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="certificado",
            constraint=models.UniqueConstraint(
                fields=("usuario", "trilha"),
                name="certificado_unico_por_usuaria_e_trilha",
            ),
        ),
        migrations.AddConstraint(
            model_name="assunto",
            constraint=models.UniqueConstraint(
                fields=("trilha", "ordem"), name="assunto_ordem_unica_por_trilha"
            ),
        ),
    ]
