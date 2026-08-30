from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Look up a value in a dict from a template, e.g. {{ my_dict|get_item:key }}."""
    if mapping is None:
        return ''
    return mapping.get(key, '')
