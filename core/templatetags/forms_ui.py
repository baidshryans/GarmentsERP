"""Template side of the lighter forms: the "More options" section and fields that show for one choice only.
The rule for opening a section is `core.forms_ui.more_open`; nothing here decides it again."""
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core import forms_ui

register = template.Library()


@register.simple_tag
def more_fields(form):
    """{% more_fields form as more %}: more.fields, more.names, more.label, more.open for a Django form."""
    return forms_ui.more_form(form)


@register.simple_tag
def more_open(values, names, *errors):
    """{% more_open vals "expected_date remarks" as open %}: for hand-written forms whose folded fields are blank
    by default. `values` is the dict the template fills its inputs from."""
    return forms_ui.more_open(values, names.split(), errors)


class MoreNode(template.Node):
    def __init__(self, nodelist, inside, options):
        self.nodelist, self.inside, self.options = nodelist, inside, options

    def render(self, context):
        opts = {k: v.resolve(context) for k, v in self.options.items()}
        cls = f"more {opts['cls']}" if opts.get("cls") else "more"
        return format_html(
            '<details class="{}"{}><summary><span class="more-title">{}</span>'
            '<span class="more-inside muted">{}</span></summary><div class="more-body">{}</div></details>',
            cls, mark_safe(" open") if opts.get("open") else "", opts.get("title") or "More options",
            self.inside.resolve(context), mark_safe(self.nodelist.render(context)))


@register.tag
def more(parser, token):
    """{% more "what is inside" open=flag title="Transport details" cls="island" %} fields {% endmore %}.
    One look and one markup for every folded section. `title` defaults to "More options"."""
    bits = token.split_contents()[1:]
    if not bits:
        raise template.TemplateSyntaxError("{% more %} needs the words that say what is inside.")
    inside, options = parser.compile_filter(bits[0]), {}
    for bit in bits[1:]:
        name, sep, value = bit.partition("=")
        if not sep or name not in ("open", "title", "cls"):
            raise template.TemplateSyntaxError(f"{{% more %}} does not understand '{bit}'.")
        options[name] = parser.compile_filter(value)
    nodelist = parser.parse(("endmore",))
    parser.delete_first_token()
    return MoreNode(nodelist, inside, options)


@register.simple_tag
def show_when(name, current, wanted, off=""):
    """Attributes for a field that applies to one choice only: {% show_when "tax_mode" d.tax_mode "template manual" %}.
    The server hides it when the choice is another one; reveal.js keeps it in step as the choice changes. Pass "off"
    as a fourth argument when a hidden field must not be sent at all (reveal.js disables it while hidden)."""
    hidden = str(current) not in wanted.split()
    return format_html('data-show-when="{}={}"{}{}', name, wanted,
                       mark_safe(" data-off-when-hidden") if off == "off" else "", mark_safe(" hidden") if hidden else "")
