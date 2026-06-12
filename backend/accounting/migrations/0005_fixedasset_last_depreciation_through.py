from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_drop_depreciation_suggestions'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixedasset',
            name='last_depreciation_through',
            field=models.DateField(blank=True, null=True),
        ),
    ]
