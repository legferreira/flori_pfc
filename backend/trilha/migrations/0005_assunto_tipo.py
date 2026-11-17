from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trilha', '0004_gestao_conteudo_e_sorteio_do_quiz'),
    ]

    operations = [
        migrations.AddField(
            model_name='assunto',
            name='tipo',
            field=models.CharField(choices=[('oficial', 'Trilha oficial'), ('extra', 'Para ir além')], default='oficial', max_length=10),
        ),
        migrations.AlterField(
            model_name='assunto',
            name='codigo',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
