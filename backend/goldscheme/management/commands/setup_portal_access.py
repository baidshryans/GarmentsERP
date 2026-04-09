from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from contacts.models import Ledger, LedgerRole
from goldscheme.models import CustomerPortalCredential


class Command(BaseCommand):
    help = 'Enable portal access for a customer by mobile number'

    def add_arguments(self, parser):
        parser.add_argument('--mobile', required=True, help='Customer mobile number')
        parser.add_argument('--password', required=True, help='Portal login password')
        parser.add_argument('--retail', required=False, help='Retail code (optional, narrows search)')

    def handle(self, *args, **options):
        mobile = options['mobile'].strip()
        password = options['password']
        retail_code = options.get('retail', '').strip() if options.get('retail') else ''

        # Find customer by mobile
        qs = Ledger.objects.filter(
            Q(mobile1=mobile) | Q(mobile2=mobile) | Q(phone1=mobile)
        )
        if retail_code:
            from mastersconfig.models import RetailMaster
            try:
                retail = RetailMaster.objects.get(retail_code=retail_code)
            except RetailMaster.DoesNotExist:
                raise CommandError(f"Retail '{retail_code}' not found.")
            qs = qs.filter(retail_code=retail)

        customer_ids = LedgerRole.objects.filter(
            ledger__in=qs, role='CO'
        ).values_list('ledger_id', flat=True)

        customer = Ledger.objects.filter(id__in=customer_ids).first()
        if not customer:
            raise CommandError(f"No customer found with mobile '{mobile}'.")

        credential, created = CustomerPortalCredential.objects.get_or_create(ledger=customer)
        credential.set_password(password)
        credential.is_active = True
        credential.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f"{action} portal access for {customer.ac_name} (mobile: {mobile})"
        ))
