from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0007_foto_url_e_logout'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='apelido',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
