"""Shared fixture helpers for customer_intel tests."""

import itertools
from decimal import Decimal


def make_retail(name="R", code="RC1"):
    from mastersconfig.models import RetailMaster

    return RetailMaster.objects.create(
        retail_name=name, retail_code=code, address_line1="addr", phone="1234567890",
    )


def make_customer(retail=None, name="Cust", mobile="9876543210", dob=None,
                  anniversary=None, email="", b2b=False, city=""):
    from contacts.models import Ledger

    ledger = Ledger.objects.create(
        ac_name=name, retail_code=retail, mobile1=mobile, dob=dob,
        anniversary=anniversary, email=email, b2b=b2b, city=city,
    )
    ledger.roles.create(role="CO")
    return ledger


def make_item(name="Ladies Ring", code="LR", group=None):
    from mastersconfig.models import Item

    return Item.objects.create(
        item_name=name, short_code=code, grp=group, item_type="M",
        uom="PCS", show_in_pcs_report=True,
    )


def make_item_group(name="Rings"):
    from mastersconfig.models import ItemGroupMaster

    return ItemGroupMaster.objects.create(item_group_name=name, short_code=name[:3])


def make_purity(value="22"):
    from goldrates.models import PurityMaster

    return PurityMaster.objects.create(purity=value, gw_per=Decimal("91.6"))


def make_barcode(retail, item, purity=None, design=None, metal_color="",
                 barcode="BC1"):
    from inventory.models import BarcodeMain

    return BarcodeMain.objects.create(
        item=item, barcode=barcode, purity=purity, design=design,
        metal_color=metal_color, retail=retail, pcs=1,
    )


def make_salesperson(retail, name="Counter"):
    from mastersconfig.models import SalesPersonMaster

    return SalesPersonMaster.objects.create(salesperson_name=name, retail=retail)


def make_sale(retail, ledger, when, mrp, discount=0, cgst=1.5, sgst=1.5,
              round_off=0, billno=None, salesperson=None):
    """A sales voucher whose bill value is derived, not stored."""
    from sales.models import SalesVou

    if salesperson is None:
        salesperson = make_salesperson(retail, f"SP{retail.id}")

    return SalesVou.objects.create(
        retail=retail, ldgr=ledger, date1=when,
        billno=billno or f"B{ledger.id}-{when:%y%m%d}-{mrp}",
        sales_person=salesperson, place_of_supply="West Bengal",
        mrp=Decimal(str(mrp)), discount=Decimal(str(discount)),
        cgst_per=Decimal(str(cgst)), sgst_per=Decimal(str(sgst)),
        igst_per=Decimal("0"), round_off=Decimal(str(round_off)),
    )


_barcode_counter = itertools.count(1)


def make_sale_line(sale, item, barcode=None, amount=1000, pcs=1, gw=5,
                   ret_status=False, making=0, making_type="per_gram", purity=0):
    """
    A sold line. `barcode` is NOT NULL on SalesVouItem, so one is minted
    automatically when the caller does not care which.
    """
    from sales.models import SalesVouItem

    if barcode is None:
        barcode = make_barcode(
            sale.retail, item, purity=make_purity("22"),
            barcode=f"AUTO{next(_barcode_counter)}",
        )

    return SalesVouItem.objects.create(
        billno=sale, item=item, barcode=barcode, pcs=pcs,
        gw=Decimal(str(gw)), amount=Decimal(str(amount)),
        making=Decimal(str(making)), making_type=making_type, purity=purity,
        ret_status=ret_status, date1=sale.date1,
    )


def make_user(username="u", superuser=False, can_view_customer_data=True,
              permissions=None, model="customerprofilesnapshot", retail=None):
    """
    A user with an optional Role granting the listed capabilities on a
    customer_intel model.

    `permissions` is a list of flag names such as ['can_get', 'can_list'].
    Passing None creates a user with a Role but no permission rows at all,
    which is the case the permission tests care about.

    Pass `retail` to grant location access — RetailMiddleware rejects a request
    with 401 when the user has no UserLocation covering the X-RETAIL-ID header,
    so any test hitting an HTTP endpoint needs it.
    """
    from django.contrib.auth.models import User
    from django.contrib.contenttypes.models import ContentType
    from contacts.models import UserLocation
    from userauth.models import Permission, Role, UserRole

    user = User.objects.create_user(username=username, password="pw")
    if retail is not None:
        location = UserLocation.objects.create(user=user, default_location=retail)
        location.location.add(retail)

    if superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user

    role = Role.objects.create(
        name=f"role-{username}", can_view_customer_data=can_view_customer_data,
    )
    UserRole.objects.create(user=user, role=role)

    if permissions:
        content_type = ContentType.objects.get(
            app_label="customer_intel", model=model,
        )
        Permission.objects.create(
            role=role, module=content_type,
            **{flag: True for flag in permissions},
        )
    return user
