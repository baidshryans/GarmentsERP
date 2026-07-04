import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import IntegrityError, transaction
from accounting.models import Account
from contacts.models import Ledger, LedgerRole
from accounting.legacy_coa_map import resolve_standard_group


class Command(BaseCommand):
    help = "Import data from CSV files into Account and Ledger models"

    def add_arguments(self, parser):
        # Optional flag to continue on errors
        parser.add_argument('--continue-on-error', action='store_true', 
                           help='Continue processing even when individual rows have errors')
        parser.add_argument('--skip-existing', action='store_true',
                           help='Skip records that would cause duplicate key errors')
        parser.add_argument('--base-path', default=None,
                           help='Directory holding the *_master.csv files (default: settings.BASE_DIR).')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        base_path = kwargs.get('base_path') or settings.BASE_DIR
        continue_on_error = kwargs.get('continue_on_error', False)
        skip_existing = kwargs.get('skip_existing', False)
        # Legacy groups (MG-*/GM-*/SG-*) are resolved to the canonical standard
        # tree via legacy_coa_map; codes without a mapping are collected here and
        # reported at the end so the map can be extended before the next sync.
        self._unmapped = set()

        if not Account.objects.filter(code="INC-DIR-SAL").exists():
            raise CommandError(
                "Standard chart of accounts not found. Run "
                "`manage.py setup_account_groups` before importaccs.")

        try:
            # Step 1: Import Main Groups
            self.stdout.write(self.style.MIGRATE_HEADING("📌 Importing Main Groups..."))
            main_groups = {}
            main_groups_file = os.path.join(base_path, "main_group.csv")
            
            if not os.path.exists(main_groups_file):
                raise FileNotFoundError(f"CSV file not found: {main_groups_file}")
                
            with open(main_groups_file, newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) < 2:
                        self.stderr.write(self.style.WARNING(f"⚠️ Invalid row in main_group.csv: {row}"))
                        continue
                        
                    pk, name = row
                    
                    legacy_code = f"MG-{pk}"
                    account = resolve_standard_group(legacy_code)
                    if account is None:
                        self._unmapped.add(f"{legacy_code} ({name})")
                        self.stderr.write(self.style.WARNING(
                            f"⚠️ Unmapped legacy main group {legacy_code} - {name}; skipping."))
                        continue
                    main_groups[pk] = account

            self.stdout.write(self.style.SUCCESS(f"🎯 Imported {len(main_groups)} main groups.\n"))

            # Step 2: Import Group Masters
            self.stdout.write(self.style.MIGRATE_HEADING("📌 Importing Group Masters..."))
            group_masters = {}
            group_masters_file = os.path.join(base_path, "group_master.csv")
            
            if not os.path.exists(group_masters_file):
                raise FileNotFoundError(f"CSV file not found: {group_masters_file}")
                
            with open(group_masters_file, newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) < 3:
                        self.stderr.write(self.style.WARNING(f"⚠️ Invalid row in group_master.csv: {row}"))
                        continue
                        
                    pk, name, mn_grp = row[0], row[1], row[2]
                    legacy_code = f"GM-{pk}"
                    account = resolve_standard_group(legacy_code)
                    if account is None:
                        self._unmapped.add(f"{legacy_code} ({name})")
                        self.stderr.write(self.style.WARNING(
                            f"⚠️ Unmapped legacy group master {legacy_code} - {name}; skipping."))
                        continue
                    group_masters[pk] = account

            self.stdout.write(self.style.SUCCESS(f"🎯 Imported {len(group_masters)} group masters.\n"))

            # Step 3: Import Subgroups
            self.stdout.write(self.style.MIGRATE_HEADING("📌 Importing Subgroups..."))
            subgroups = {}
            subgroups_file = os.path.join(base_path, "subgroup_master.csv")
            
            if not os.path.exists(subgroups_file):
                raise FileNotFoundError(f"CSV file not found: {subgroups_file}")
                
            with open(subgroups_file, newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) < 3:
                        self.stderr.write(self.style.WARNING(f"⚠️ Invalid row in subgroup_master.csv: {row}"))
                        continue
                        
                    pk, name, grp = row[0], row[1], row[2]
                    legacy_code = f"SG-{pk}"
                    account = resolve_standard_group(legacy_code)
                    if account is None:
                        self._unmapped.add(f"{legacy_code} ({name})")
                        self.stderr.write(self.style.WARNING(
                            f"⚠️ Unmapped legacy subgroup {legacy_code} - {name}; skipping."))
                        continue
                    subgroups[pk] = account

            self.stdout.write(self.style.SUCCESS(f"🎯 Imported {len(subgroups)} subgroups.\n"))


            # Step 4: Import Ledger Data
            self.stdout.write(self.style.MIGRATE_HEADING("📌 Importing Ledger Data..."))
            ledger_count = 0
            ledger_file = os.path.join(base_path, "ledger_master.csv")
            
            if not os.path.exists(ledger_file):
                raise FileNotFoundError(f"CSV file not found: {ledger_file}")
                
            with open(ledger_file, newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                header = next(reader)  # Skip header

                for row in reader:  # Start at 2 to account for header row
                    row = dict(zip(header, row))   
                    try:
                        if len(row) < 4:
                            self.stderr.write(self.style.WARNING(f"⚠️ Row {row['id']}: Not enough columns in ledger_master.csv"))
                            continue
                            
                        ac_name = row["ac_name"]  # Ledger Name
                        
                        # Get mobile number if available (assuming it's in column 1, adjust index as needed)
                        mobile1 = None
                        if len(row) > 1 and row["mobile1"]:
                            mobile1 = row["mobile1"]
                            
                        # Get other fields that might be needed
                        mobile2 = None
                        
                        # Safely get type with fallback to "OTH"
                        type = "OTH"  # Default value
                        if len(row) > 16 and row["ledger_type"]:
                            type = row["ledger_type"]
                        print(type) 
                        # Validate ledger type (example - adjust according to your valid types)
                        valid_types = ["OTH", "CO", "DL", "EXP","REF" ,"SC","SD","KR","INC","HM"]

                        if type not in valid_types:
                            self.stderr.write(self.style.WARNING(
                                f"⚠️ Row {row['id']}: Invalid type '{type}' for ledger '{ac_name}', using 'OTH' instead"))
                            type = "OTH"
                            
                        # Safely get group_code
                        group_code = None
                       
                        group_code = row["gr_code"]
                        # print(group_code)
                        # Determine ac_group
                        ac_group = None
                        if group_code:
                            parts = group_code.split("-")
                            if len(parts) == 3 and parts[2] in subgroups:
                                ac_group = subgroups.get(parts[2])  # Last level (subgroup)
                            elif len(parts) == 2 and parts[1] in group_masters:
                                ac_group = group_masters.get(parts[1])  # Group Master
                            elif len(parts) == 1 and parts[0] in main_groups:
                                ac_group = main_groups.get(parts[0])  # Main Group

                        # if not ac_group:
                        #     self.stderr.write(self.style.WARNING(
                        #         f"⚠️ Row {i}: No matching group found for {group_code} (Ledger: {ac_name})"))
                        
                        # Check if ledger already exists
                        ledger = Ledger.objects.filter(id=row["id"],ac_name=ac_name).first()
                        
                        if ledger:
                            # Update existing ledger if necessary
                            if ledger.ac_group != ac_group:
                                ledger.ac_group = ac_group
                                ledger.save(update_fields=['ac_group'])
                            # Ensure the role exists (is_primary only if no roles yet)
                            is_first = not ledger.roles.exists()
                            LedgerRole.objects.get_or_create(
                                ledger=ledger, role=type,
                                defaults={'is_primary': is_first}
                            )
                        else:
                            # Create new ledger with potential mobile number
                            try:
                                ledger = Ledger.objects.create(
                                    id=row["id"],
                                    ac_name=ac_name,
                                    ac_group=ac_group,
                                    mobile1=mobile1 if mobile1 else ac_name,
                                    mobile2=mobile2
                                )
                                LedgerRole.objects.create(ledger=ledger, role=type, is_primary=True)
                                # self.stdout.write(f"✅ Row {i}: Created Ledger: {ac_name} ({group_code})")
                            except IntegrityError as e:
                                # If there's a unique constraint error on mobile1, append account name
                                if "mobile1" in str(e) and mobile1:
                                    modified_mobile = f"{mobile1}_{ac_name.replace(' ', '')}"
                                    self.stderr.write(self.style.WARNING(
                                        f"⚠️ Row {row['id']}: Mobile number {mobile1} already exists. Using {modified_mobile} instead."))
                                    ledger = Ledger.objects.create(
                                        id=row["id"],
                                        ac_name=ac_name,
                                        ac_group=ac_group,
                                        mobile1=modified_mobile,
                                        mobile2=mobile2
                                    )
                                    LedgerRole.objects.create(ledger=ledger, role=type, is_primary=True)
                                else:
                                    # Re-raise if it's not a mobile1 issue or if handling fails
                                    raise
                                
                        ledger_count += 1

                    except Exception as e:
                        raise e
                        error_msg = f"❌ Error processing row {row['id']}: {e}"
                        if continue_on_error:
                            self.stderr.write(self.style.ERROR(error_msg))
                        else:
                            raise CommandError(error_msg)

            # This line was indented correctly now
            self.stdout.write(self.style.SUCCESS(f"🎉 Ledger import completed successfully. Imported {ledger_count} ledgers."))
            if self._unmapped:
                self.stdout.write(self.style.WARNING(
                    "⚠️ Unmapped legacy groups (add to accounting/legacy_coa_map.py): "
                    + ", ".join(sorted(self._unmapped))))
            
        except FileNotFoundError as e:
            self.stderr.write(self.style.ERROR(f"{e}"))
            return
        except CommandError as e:
            self.stderr.write(self.style.ERROR(f"{e}"))
            return
        except Exception as e:
            raise e
            self.stderr.write(self.style.ERROR(f"❌ Fatal error: {e}"))
            return