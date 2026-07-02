from datetime import date, time
from django.test import TestCase


def make_retail(name="R", code="RC1", series="BS1"):
    from mastersconfig.models import RetailMaster
    return RetailMaster.objects.create(
        retail_name=name, retail_code=code, address_line1="addr",
        phone="1234567890", bill_series=series,
    )


def make_customer(retail, name, dob=None, anniversary=None, mobile="9876543210"):
    from contacts.models import Ledger
    led = Ledger.objects.create(
        ac_name=name, retail_code=retail, mobile1=mobile,
        dob=dob, anniversary=anniversary,
    )
    led.roles.create(role="CO")
    return led


class FindDueRecipientsTests(TestCase):
    def _settings(self, retail):
        from mastersconfig.models import CRMSettings
        return CRMSettings.objects.create(
            retail=retail, is_enabled=True, provider="webhook", send_time=time(9, 0),
        )

    def test_returns_birthday_recipient_for_today(self):
        from contacts.crm_sender import find_due_recipients

        retail = make_retail()
        settings = self._settings(retail)
        led = make_customer(retail, "Asha", dob=date(1990, 7, 2))

        recipients = find_due_recipients(settings, date(2026, 7, 2))

        self.assertIn((led.id, "birthday"), recipients)

    def test_excludes_non_matching_dates(self):
        from contacts.crm_sender import find_due_recipients

        retail = make_retail()
        settings = self._settings(retail)
        make_customer(retail, "Ravi", dob=date(1985, 1, 1))

        recipients = find_due_recipients(settings, date(2026, 7, 2))

        self.assertEqual(recipients, [])

    def test_excludes_other_retail(self):
        from contacts.crm_sender import find_due_recipients

        retail_a = make_retail(name="A", code="RCA", series="BSA")
        retail_b = make_retail(name="B", code="RCB", series="BSB")
        settings_a = self._settings(retail_a)
        make_customer(retail_b, "Meena", dob=date(1990, 7, 2))

        recipients = find_due_recipients(settings_a, date(2026, 7, 2))

        self.assertEqual(recipients, [])
