from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trilha', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fonte',
            name='url',
            field=models.URLField(max_length=255, unique=True),
        ),
    ]
