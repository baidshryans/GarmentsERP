from django import template
from global_vars import *

register = template.Library()

@register.simple_tag
def get_states_of_india():
    return STATES_OF_INDIA

@register.simple_tag
def get_customer_type():
    return CUSTOMER_TYPE