from .models import BarcodeTransaction
import base64
import qrcode
import random
from io import BytesIO
import os
from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from .models import *
from accounting.utils import increment_series_no


def insert_barcode_transaction(date, barcode, billno, trans_type, user, ip_address):
    """
    Inserts a barcode transaction and updates the ItemWallet count based on the transaction type.
    
    Args:
        date (datetime): The transaction date.
        barcode (BarcodeMain): The barcode instance.
        billno (str): The bill number.
        trans_type (str): The transaction type ("add" or "subtract").
        user (User): The user instance.
        ip_address (str): The IP address of the user.
    """
    try:
        # Ensure atomicity of database operations
        with transaction.atomic():
            # Create the barcode transaction
            BarcodeTransaction.objects.create(
                date=date,
                barcode=barcode,
                billno=billno,
                trans_type=trans_type,
                user=user,
                ip_address=ip_address
            )

            # Get the associated ItemWallet
            item_wallet = ItemWallet.objects.select_for_update().get(item=barcode.item)

            # Update the item_count based on the transaction type
            if trans_type == "add":
                item_wallet.item_count += 1
            elif trans_type == "subtract":
                if item_wallet.item_count > 0:
                    item_wallet.item_count -= 1
                else:
                    raise ValueError("Cannot subtract from an empty wallet.")

            # Save the updated item wallet
            item_wallet.save()

    except ItemWallet.DoesNotExist:
        raise ValueError(f"ItemWallet not found for item: {barcode.item}")
    except Exception as e:
        raise ValueError(f"Error while processing transaction: {e}")
    
    
def generate_ean13():
    while True:
        code = ''.join([str(random.randint(0, 9)) for _ in range(12)])
        total = sum(int(code[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
        check_digit = (10 - (total % 10)) % 10
        ean13 = code + str(check_digit)
        #if not BarcodeMain.objects.filter(barcode=ean13).exists():
        return ean13

def generate_qr_code_image(ean_code):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(ean_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Create the qr_code directory if it doesn't exist
    qr_code_dir = os.path.join(settings.MEDIA_ROOT, 'qr_code')
    os.makedirs(qr_code_dir, exist_ok=True)
    
    # Save the QR code image
    file_name = f"{ean_code}.png"
    file_path = os.path.join(qr_code_dir, file_name)
    img.save(file_path)
    
    # Return the relative path to the saved image
    return os.path.join('qr_code', file_name)

def insert_design_records(date, design_no, main_item, pcs, gw, making, making_type, details):
    # Create DesignMain record
    from .models import DesignMain, DesignDetails

    design_main = DesignMain.objects.create(
        date=date,
        design_no=design_no,
        item=main_item,
        pcs=pcs,
        gw=gw,
        making=making,
        making_type=making_type
    )

    # Create DesignDetails records
    for detail in details:
        DesignDetails.objects.create(
            design_no=design_main,
            item=detail['item'],
            pcs=detail['pcs'],
            ct=detail['ct'],
            rate=detail['rate'],
            amt=detail['amt']
        )

def generate_stock_journal_billno(retail):
    from accounting.utils import get_next_bill_number
    return get_next_bill_number(retail, "SJ")