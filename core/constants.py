"""Static reference data. GST state codes follow the GSTIN numbering."""

INDIAN_STATES = [
    ("01", "Jammu & Kashmir"), ("02", "Himachal Pradesh"), ("03", "Punjab"), ("04", "Chandigarh"),
    ("05", "Uttarakhand"), ("06", "Haryana"), ("07", "Delhi"), ("08", "Rajasthan"),
    ("09", "Uttar Pradesh"), ("10", "Bihar"), ("11", "Sikkim"), ("12", "Arunachal Pradesh"),
    ("13", "Nagaland"), ("14", "Manipur"), ("15", "Mizoram"), ("16", "Tripura"),
    ("17", "Meghalaya"), ("18", "Assam"), ("19", "West Bengal"), ("20", "Jharkhand"),
    ("21", "Odisha"), ("22", "Chhattisgarh"), ("23", "Madhya Pradesh"), ("24", "Gujarat"),
    ("26", "Dadra & Nagar Haveli and Daman & Diu"), ("27", "Maharashtra"), ("29", "Karnataka"),
    ("30", "Goa"), ("31", "Lakshadweep"), ("32", "Kerala"), ("33", "Tamil Nadu"),
    ("34", "Puducherry"), ("35", "Andaman & Nicobar Islands"), ("36", "Telangana"),
    ("37", "Andhra Pradesh"), ("38", "Ladakh"), ("97", "Other Territory"),
]
STATE_NAMES = dict(INDIAN_STATES)

PERMISSION_ACTIONS = ["view", "create", "edit", "cancel", "approve"]

# Fields hidden (not greyed) from roles without an explicit grant (PRD section 7).
SENSITIVE_FIELDS = {
    "cost": "Cost price",
    "margin": "Margin",
    "customer_phone": "Customer phone number",
}
