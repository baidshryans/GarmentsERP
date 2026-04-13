CUSTOMER_SENSITIVE_FIELDS = {
    'ac_name', 'display_name', 'salutation',
    'phone1', 'phone2', 'phone3',
    'mobile1', 'mobile2', 'mobile3',
    'email', 'fax',
    'add1', 'add2', 'city', 'pincode', 'state',
    'ship_add1', 'ship_add2', 'ship_city', 'ship_pincode', 'ship_state',
    'pan', 'gst', 'aadhar', 'passport', 'dl_no',
    'dob', 'anniversary', 'remarks',
}

MASK_VALUE = '****'


def is_customer_ledger(obj):
    """Check if a Ledger instance has the Customer (CO) role."""
    if hasattr(obj, '_prefetched_objects_cache') and 'roles' in obj._prefetched_objects_cache:
        return any(r.role == 'CO' for r in obj._prefetched_objects_cache['roles'])
    return obj.roles.filter(role='CO').exists()


def mask_ledger_representation(ret, obj):
    """Mask sensitive fields in-place for a customer ledger."""
    if not is_customer_ledger(obj):
        return ret
    for field in CUSTOMER_SENSITIVE_FIELDS:
        if field in ret and ret[field]:
            ret[field] = MASK_VALUE
    return ret
