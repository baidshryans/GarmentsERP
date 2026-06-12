from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_initial'),
    ]

    operations = [
        migrations.DeleteModel(name='DepreciationSuggestionLine'),
        migrations.DeleteModel(name='DepreciationSuggestion'),
    ]
