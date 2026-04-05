from accounting.utils import get_next_bill_number


def generate_next_sale_voucher_no(retail):
    return get_next_bill_number(retail, "SV")


def generate_next_sale_return_no(retail):
    return get_next_bill_number(retail, "SR")


def generate_next_sale_app_no(retail):
    return get_next_bill_number(retail, "SA")
