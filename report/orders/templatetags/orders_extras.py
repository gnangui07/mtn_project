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

@register.filter
def split(value, delimiter=','):
    """
    Split a string by delimiter.
    Usage: {{ "0,1,2,3,4,5,6,7,8,9,10"|split:"," }}
    """
    if value is None:
        return []
    return str(value).split(delimiter)

@register.filter
def range_list(value):
    """
    Create a list of integers from 0 to value (inclusive).
    Usage: {{ 10|range_list }} -> [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    """
    try:
        return list(range(int(value) + 1))
    except (ValueError, TypeError):
        return []

