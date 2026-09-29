from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_enfile_nom_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='EtatFile',
            fields=[
                ('nom_file', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('en_pause', models.BooleanField(default=False)),
                ('mise_en_pause_le', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AddField(
            model_name='enfile',
            name='date_appel',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enfile',
            name='secondes_pause',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='enfile',
            name='secondes_pause_appel',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
