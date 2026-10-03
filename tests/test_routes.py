"""Route audit: every URL resolves, nothing is duplicated, nothing opens without a login, nothing returns a 500."""
import re
from pathlib import Path

import pytest
from django.test import Client
from django.urls import NoReverseMatch, URLPattern, URLResolver, get_resolver, reverse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = {"login"}                                   # reachable without signing in
POST_ONLY = {"logout"}                               # a GET is refused (405)
SKIP_PREFIXES = ("admin:", "api")                    # Django admin and the REST API have their own tests


def walk(patterns, prefix="", namespace=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            ns = namespace + (p.namespace + ":" if p.namespace else "")
            yield from walk(p.url_patterns, prefix + str(p.pattern), ns)
        elif isinstance(p, URLPattern):
            yield namespace + (p.name or ""), prefix + str(p.pattern), p


ROUTES = [(n, r, p) for n, r, p in walk(get_resolver().url_patterns) if n and not n.startswith(SKIP_PREFIXES)]
ARG_ROUTES = [(n, r) for n, r, p in ROUTES if "<" in r]
PLAIN_ROUTES = [n for n, r, p in ROUTES if "<" not in r]


def _args(route):
    return [999999 if tok.startswith("int:") else "x" for tok in re.findall(r"<([^>]+)>", route)]


def test_route_names_and_paths_are_unique():
    names, paths = {}, {}
    for n, r, p in ROUTES:
        assert n not in names, f"route name '{n}' is used twice: {names[n]} and {r}"
        names[n] = r
        key = (r, tuple(sorted((p.default_args or {}).items())))
        assert key not in paths, f"path {r} is registered twice ({paths[key]} and {n})"
        paths[key] = n


def test_every_url_name_used_in_a_template_or_redirect_exists():
    known = {n for n, _, _ in ROUTES} | {n for n, _, _ in walk(get_resolver().url_patterns)}
    missing = []
    for path in [*ROOT.glob("templates/**/*.html"), *ROOT.glob("*/templates/**/*.html")]:
        for name in re.findall(r"\{%\s*url\s+['\"]([\w:-]+)['\"]", path.read_text(encoding="utf-8")):
            if name not in known:
                missing.append(f"{path.relative_to(ROOT)}: {name}")
    for path in [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "tests" not in p.parts and "migrations" not in p.parts]:
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"(?:redirect|reverse|reverse_lazy)\(\s*['\"]([\w:-]+)['\"]", text):
            if name not in known:
                missing.append(f"{path.relative_to(ROOT)}: {name}")
    assert not missing, missing


def test_every_menu_entry_points_at_a_real_screen():
    from core.context_processors import NAV

    for group, items in NAV:
        for url_name, label, screen in items:
            try:
                reverse(url_name)
            except NoReverseMatch:
                pytest.fail(f"menu entry '{label}' in {group} points at '{url_name}', which has no route")


@pytest.mark.parametrize("name", PLAIN_ROUTES)
def test_screens_open_for_the_owner_and_never_error(company, admin_user, name):
    c = Client()
    c.force_login(admin_user)
    r = c.get(reverse(name))
    if name in POST_ONLY:
        assert r.status_code == 405
    else:
        assert r.status_code in (200, 302), f"{name} answered {r.status_code}"


@pytest.mark.parametrize("name", PLAIN_ROUTES)
def test_nothing_opens_without_signing_in(company, name):
    r = Client().get(reverse(name))
    if name in PUBLIC:
        assert r.status_code == 200
    elif name in POST_ONLY:
        assert r.status_code == 405
    else:
        assert r.status_code in (302, 403) and (r.status_code == 403 or "/accounts/login/" in r["Location"] or "/setup" in r["Location"]), name


@pytest.mark.parametrize("name,route", ARG_ROUTES)
def test_unknown_record_is_a_404_not_a_crash(company, admin_user, name, route):
    c = Client()
    c.force_login(admin_user)
    r = c.get(reverse(name, args=_args(route)))
    assert r.status_code in (404, 302, 405), f"{name} answered {r.status_code} for a record that does not exist"
