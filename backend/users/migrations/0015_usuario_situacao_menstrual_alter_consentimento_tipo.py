from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_log_admin_user_excluido'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='situacao_menstrual',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='consentimento',
            name='tipo',
            field=models.CharField(choices=[('termos_uso', 'Termos de uso'), ('politica_privacidade', 'Política de privacidade'), ('saude', 'Dados de saúde')], max_length=30),
        ),
    ]
