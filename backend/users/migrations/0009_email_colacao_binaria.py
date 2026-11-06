from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0008_alter_usuario_apelido'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='email',
            field=models.EmailField(blank=True, db_collation='utf8mb4_bin', max_length=150, null=True, unique=True),
        ),
    ]
