def convert_empty_to_none_or_zero(value):
    if value == "":
        return None
    return value

from global_vars import STATES_OF_INDIA

def get_place_of_supply_display(place_of_supply):
    for state_code, state_name in STATES_OF_INDIA:
        if state_code == place_of_supply:
            return state_name
    return None  # Return None if no match is found


def get_user_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
