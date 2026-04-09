STATES_OF_INDIA = [
    ("AP", "Andhra Pradesh"),
    ("AR", "Arunachal Pradesh"),
    ("AS", "Assam"),
    ("BR", "Bihar"),
    ("CT", "Chhattisgarh"),
    ("GA", "Goa"),
    ("GJ", "Gujarat"),
    ("HR", "Haryana"),
    ("HP", "Himachal Pradesh"),
    ("JK", "Jammu and Kashmir"),
    ("JH", "Jharkhand"),
    ("KA", "Karnataka"),
    ("KL", "Kerala"),
    ("MP", "Madhya Pradesh"),
    ("MH", "Maharashtra"),
    ("MN", "Manipur"),
    ("ML", "Meghalaya"),
    ("MZ", "Mizoram"),
    ("NL", "Nagaland"),
    ("OR", "Odisha"),
    ("PB", "Punjab"),
    ("RJ", "Rajasthan"),
    ("SK", "Sikkim"),
    ("TN", "Tamil Nadu"),
    ("TG", "Telangana"),
    ("TR", "Tripura"),
    ("UP", "Uttar Pradesh"),
    ("UT", "Uttarakhand"),
    ("WB", "West Bengal"),
    ("AN", "Andaman and Nicobar Islands"),
    ("CH", "Chandigarh"),
    ("DN", "Dadra and Nagar Haveli"),
    ("DD", "Daman and Diu"),
    ("DL", "Delhi"),
    ("LD", "Lakshadweep"),
    ("PY", "Puducherry"),
]

CUSTOMER_TYPE = [
    ("CO", "CUSTOMER"),
    ("CA","CASH"),
    ("BA","BANK"),
    ("KR","KARIGAR"),
    ("VD","VENDOR"),
    ("DL","DEALER"),
    ("REF","REFINERY"),
    ("MLT","MELTING HOUSE"),
    ("HM","HALLMARK"),
    ("INC","INCOME"),
    ("EXP","EXPENSE"),
    ("OTH","OTHER"),
]

class VoucherType:
    journal = "JRNL"
    pmnt = "PMNT"
    cntr = "CNTR"
    sale = "SALE"
    sale_rep = "SALE-REP"
    purc_co = "PURC-CO" 
    purc_sc = "PURC-SC"
    purc_ret = "PURC-RET"
    sale_ret = "SALE-RET"
    rcpt = "RCPT"
    rcpt_sale = "RCPT-SALE"
    credit_note = "CN"
    debit_note = "DN"
    scheme = "SCHM"
    scheme_redeem = "SCHM-R"
