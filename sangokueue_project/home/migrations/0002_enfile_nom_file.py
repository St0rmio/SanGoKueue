from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='enfile',
            name='nom_file',
            field=models.CharField(default='', max_length=64),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='enfile',
            constraint=models.UniqueConstraint(
                fields=('numero_de_billet', 'nom_file'),
                name='unique_billet_dans_file',
            ),
        ),
    ]
