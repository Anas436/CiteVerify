from django import template

register = template.Library()


@register.filter
def splitlines(value):
    if isinstance(value, str):
        return [line.strip() for line in value.replace('\r\n', '\n').split('\n') if line.strip()]
    return value
