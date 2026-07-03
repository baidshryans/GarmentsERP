from django.db import migrations


def consolidate(apps, schema_editor):
    FiscalYearMaster = apps.get_model('mastersconfig', 'FiscalYearMaster')
    RetailMaster = apps.get_model('mastersconfig', 'RetailMaster')
    SystemSettings = apps.get_model('mastersconfig', 'SystemSettings')

    fys = list(FiscalYearMaster.objects.all())
    if not fys:
        return

    import datetime
    active_code = None
    ho = RetailMaster.objects.filter(active_fy__isnull=False).order_by('id').first()
    if ho and ho.active_fy_id:
        active_code = FiscalYearMaster.objects.get(pk=ho.active_fy_id).fy_code
    if active_code is None:
        today = datetime.date.today()
        covering = next((f for f in fys if f.fy_start <= today <= f.fy_end), None)
        active_code = (covering or max(fys, key=lambda f: f.fy_start)).fy_code

    canon = {}
    for f in sorted(fys, key=lambda x: x.id):
        c = canon.get(f.fy_code)
        if c is None:
            canon[f.fy_code] = f
        else:
            if f.is_closed:
                c.is_closed = True
            if f.is_hard_closed:
                c.is_hard_closed = True
    for c in canon.values():
        c.save(update_fields=['is_closed', 'is_hard_closed'])

    old_to_canon = {f.id: canon[f.fy_code].id for f in fys}

    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, 'is_relation', False):
                continue
            if getattr(field, 'many_to_one', False) and field.related_model is FiscalYearMaster:
                col = field.attname  # e.g. 'fiscal_year_id'
                for old_id, new_id in old_to_canon.items():
                    if old_id == new_id:
                        continue
                    model.objects.filter(**{col: old_id}).update(**{col: new_id})

    keep_ids = {c.id for c in canon.values()}
    FiscalYearMaster.objects.exclude(id__in=keep_ids).delete()

    active_fy = canon[active_code]
    RetailMaster.objects.update(active_fy=active_fy)

    ss, _ = SystemSettings.objects.get_or_create(pk=1, defaults={'attachment_storage_path': ''})
    ss.active_fy = active_fy
    ss.save(update_fields=['active_fy'])


class Migration(migrations.Migration):
    dependencies = [
        ('mastersconfig', '0008_systemsettings_active_fy'),
        ('sales', '0004_customerorder_uniq_co_number_and_more'),
        ('purchase', '0005_purchasevoucher_uniq_pv_number'),
        ('inventory', '0019_interretailtransfervoucher_uniq_irtv_number'),
        ('accounting', '0010_cashgoldconversion_uniq_cgconv_number_and_more'),
        ('manufacturing', '0008_hallmarkissue_uniq_hmkissue_number_and_more'),
        ('goldscheme', '0011_customerportalotp_purpose'),
        ('hr', '0003_hrsettings_esi_ceiling_hrsettings_esi_employee_rate_and_more'),
    ]
    operations = [migrations.RunPython(consolidate, migrations.RunPython.noop)]
