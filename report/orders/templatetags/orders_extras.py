from django import template
import collections

register = template.Library()

@register.filter
def is_dict(value):
    """
    Check if value is a dictionary-like object.
    Usage: {{ value|is_dict }}
    """
    return isinstance(value, collections.abc.Mapping)

@register.filter
def get_item(dictionary, key):
    """
    Filter to access dictionary items by key in templates.
    Usage: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None or not isinstance(dictionary, collections.abc.Mapping):
        return ''
    return dictionary.get(key, '')
