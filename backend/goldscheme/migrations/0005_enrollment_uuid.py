import uuid

from django.db import migrations, models


def backfill_uuids(apps, schema_editor):
    SchemeEnrollment = apps.get_model('goldscheme', 'SchemeEnrollment')
    for row in SchemeEnrollment.objects.filter(uuid__isnull=True).only('id'):
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('goldscheme', '0004_schemenominee_enrollment_form_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemeenrollment',
            name='uuid',
            field=models.UUIDField(null=True, editable=False, db_index=True),
        ),
        migrations.RunPython(backfill_uuids, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='schemeenrollment',
            name='uuid',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                db_index=True,
                help_text='Opaque public identifier used in customer-facing URLs.',
            ),
        ),
    ]
