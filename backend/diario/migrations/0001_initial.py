import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0015_usuario_situacao_menstrual_alter_consentimento_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sintoma',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('codigo', models.CharField(max_length=30, unique=True)),
                ('nome', models.CharField(max_length=60)),
                ('ativo', models.BooleanField(default=True)),
                ('ordem', models.PositiveSmallIntegerField(default=1)),
            ],
            options={
                'db_table': 'diario_sintomas',
                'ordering': ['ordem', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='RegistroDiario',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('data', models.DateField()),
                ('fluxo', models.CharField(blank=True, max_length=10, null=True)),
                ('humor', models.CharField(blank=True, max_length=10, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registros_diario', to='users.usuario')),
            ],
            options={
                'db_table': 'diario_registros',
                'ordering': ['data'],
            },
        ),
        migrations.CreateModel(
            name='RegistroSintoma',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('intensidade', models.CharField(max_length=10)),
                ('registro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sintomas', to='diario.registrodiario')),
                ('sintoma', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registros', to='diario.sintoma')),
            ],
            options={
                'db_table': 'diario_registros_sintomas',
            },
        ),
        migrations.AddConstraint(
            model_name='registrodiario',
            constraint=models.UniqueConstraint(fields=('usuario', 'data'), name='registro_diario_unico_por_dia'),
        ),
        migrations.AddConstraint(
            model_name='registrosintoma',
            constraint=models.UniqueConstraint(fields=('registro', 'sintoma'), name='sintoma_unico_por_registro'),
        ),
    ]
