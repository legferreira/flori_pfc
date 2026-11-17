from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trilha', '0002_fonte_url_255'),
    ]

    operations = [
        migrations.AddField(
            model_name='assunto',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='card',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='fonte',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='opcao',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='pergunta',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddConstraint(
            model_name='opcao',
            constraint=models.UniqueConstraint(fields=('pergunta', 'ordem'), name='opcao_ordem_unica_por_pergunta'),
        ),
        migrations.AddConstraint(
            model_name='pergunta',
            constraint=models.UniqueConstraint(fields=('trilha', 'ordem'), name='pergunta_ordem_unica_por_trilha'),
        ),
    ]
