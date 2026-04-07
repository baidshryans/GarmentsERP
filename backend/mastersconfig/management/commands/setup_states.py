"""
Seed all Indian states and union territories into the State master.
Safe to run multiple times — uses update_or_create.
"""
from django.core.management.base import BaseCommand
from mastersconfig.models import State

INDIAN_STATES = [
    # id, name, type, tin, code
    (1,  "Jammu & Kashmir",            "STATE", 1,  "01"),
    (2,  "Himachal Pradesh",           "STATE", 2,  "02"),
    (3,  "Punjab",                     "STATE", 3,  "03"),
    (4,  "Chandigarh",                 "UT",    4,  "04"),
    (5,  "Uttarakhand",                "STATE", 5,  "05"),
    (6,  "Haryana",                    "STATE", 6,  "06"),
    (7,  "Delhi",                      "UT",    7,  "07"),
    (8,  "Rajasthan",                  "STATE", 8,  "08"),
    (9,  "Uttar Pradesh",              "STATE", 9,  "09"),
    (10, "Bihar",                      "STATE", 10, "10"),
    (11, "Sikkim",                     "STATE", 11, "11"),
    (12, "Arunachal Pradesh",          "STATE", 12, "12"),
    (13, "Nagaland",                   "STATE", 13, "13"),
    (14, "Manipur",                    "STATE", 14, "14"),
    (15, "Mizoram",                    "STATE", 15, "15"),
    (16, "Tripura",                    "STATE", 16, "16"),
    (17, "Meghalaya",                  "STATE", 17, "17"),
    (18, "Assam",                      "STATE", 18, "18"),
    (19, "West Bengal",                "STATE", 19, "19"),
    (20, "Jharkhand",                  "STATE", 20, "20"),
    (21, "Odisha",                     "STATE", 21, "21"),
    (22, "Chhattisgarh",               "STATE", 22, "22"),
    (23, "Madhya Pradesh",             "STATE", 23, "23"),
    (24, "Gujarat",                    "STATE", 24, "24"),
    (25, "Daman & Diu",                "UT",    25, "25"),
    (26, "Dadra & Nagar Haveli",       "UT",    26, "26"),
    (27, "Maharashtra",                "STATE", 27, "27"),
    (28, "Andhra Pradesh",             "STATE", 28, "28"),
    (29, "Karnataka",                  "STATE", 29, "29"),
    (30, "Goa",                        "STATE", 30, "30"),
    (31, "Lakshadweep",                "UT",    31, "31"),
    (32, "Kerala",                     "STATE", 32, "32"),
    (33, "Tamil Nadu",                 "STATE", 33, "33"),
    (34, "Puducherry",                 "UT",    34, "34"),
    (35, "Andaman & Nicobar Islands",  "UT",    35, "35"),
    (36, "Telangana",                  "STATE", 36, "36"),
    (37, "Ladakh",                     "UT",    37, "38"),
]


class Command(BaseCommand):
    help = "Seed all Indian states and union territories into the State master."

    def handle(self, *args, **kwargs):
        created_count = 0
        updated_count = 0
        for sid, name, stype, tin, code in INDIAN_STATES:
            _, created = State.objects.update_or_create(
                id=sid,
                defaults={"name": name, "type": stype, "tin": tin, "code": code},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"States seeded: {created_count} created, {updated_count} updated."
            )
        )
