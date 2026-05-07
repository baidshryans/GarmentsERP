from accounting.utils import get_next_bill_number


def generate_next_sale_voucher_no(retail):
    return get_next_bill_number(retail, "SV")


def generate_next_sale_return_no(retail):
    return get_next_bill_number(retail, "SR")


def generate_next_sale_app_no(retail):
    return get_next_bill_number(retail, "SA")

import json
import decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)
