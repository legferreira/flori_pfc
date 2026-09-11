import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """User -> Usuario, e o aceite dos termos vira a tabela de consentimentos.

    O autodetector propôs CreateModel(Usuario) + DeleteModel(User), o que apagaria
    a tabela 'users'. Como as duas classes apontam para a mesma db_table, um
    RenameModel resolve sem tocar nos dados.
    """

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='User',
            new_name='Usuario',
        ),
        migrations.AlterField(
            model_name='usuario',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
            ),
        ),
        # O aceite deixa de ser um booleano na usuária: passa a ser registro datado.
        migrations.RemoveField(
            model_name='usuario',
            name='termos_aceitos',
        ),
        migrations.CreateModel(
            name='Consentimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('termos_uso', 'Termos de uso'), ('politica_privacidade', 'Política de privacidade')], max_length=30)),
                ('versao_documento', models.CharField(max_length=20)),
                ('aceito', models.BooleanField()),
                ('data_consentimento', models.DateTimeField(auto_now_add=True)),
                ('ip_origem', models.GenericIPAddressField(blank=True, null=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='consentimentos', to='users.usuario')),
            ],
            options={
                'db_table': 'consentimentos',
            },
        ),
        migrations.AddIndex(
            model_name='consentimento',
            index=models.Index(fields=['usuario', 'tipo', '-data_consentimento'], name='consentimen_usuario_8c9dd9_idx'),
        ),
    ]
