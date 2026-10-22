"""Exhaustive tests for whitelist patch engine in backend/patcher.py."""

from backend.patcher import apply_patch, dry_run
from backend.schemas import (
    AddCss,
    ChangeTag,
    RemoveAttr,
    SetAttr,
    SetText,
    WrapLabel,
)


def test_set_attr_happy_path():
    html = '<div><img id="logo" src="logo.png"></div>'
    patch = SetAttr(selector="#logo", name="alt", value="Sunrise College Logo")
    res = apply_patch(html, patch)
    assert res.ok
    assert 'alt="Sunrise College Logo"' in res.html_after
    assert res.diff != ""
    assert res.before_snippet != res.after_snippet


def test_remove_attr_happy_path():
    html = '<div id="banner" role="banner" aria-hidden="true"></div>'
    patch = RemoveAttr(selector="#banner", name="aria-hidden")
    res = apply_patch(html, patch)
    assert res.ok
    assert "aria-hidden" not in res.html_after
    assert 'role="banner"' in res.html_after


def test_set_text_happy_path():
    html = '<p><a id="cta" href="/apply">Click here</a></p>'
    patch = SetText(selector="#cta", value="Read admissions guidelines")
    res = apply_patch(html, patch)
    assert res.ok
    assert "Read admissions guidelines</a>" in res.html_after
    assert "Click here" not in res.html_after


def test_wrap_label_happy_path_and_id_generation():
    html = '<form><input type="email" placeholder="Email"></form>'
    patch = WrapLabel(selector="input[type='email']", label_text="Email address")
    res = apply_patch(html, patch)
    assert res.ok
    assert '<label for="a11y-field-1">Email address</label>' in res.html_after
    assert 'id="a11y-field-1"' in res.html_after


def test_add_css_happy_path():
    html = '<p class="note" style="margin: 10px;">Warning</p>'
    patch = AddCss(selector="p.note", property="color", value="#222222")
    res = apply_patch(html, patch)
    assert res.ok
    assert "color: #222222;" in res.html_after
    assert "margin: 10px;" in res.html_after


def test_change_tag_happy_path():
    html = '<div><h4 class="title">Section Title</h4></div>'
    patch = ChangeTag(selector="h4.title", new_tag="h2")
    res = apply_patch(html, patch)
    assert res.ok
    assert '<h2 class="title">Section Title</h2>' in res.html_after


# ---- Rejection and Safety Tests ----


def test_reject_event_handlers():
    html = '<button id="btn">Click</button>'
    patch = SetAttr(selector="#btn", name="onclick", value="alert(1)")
    res = apply_patch(html, patch)
    assert not res.ok
    assert "forbidden" in res.error.lower()


def test_reject_src_and_href():
    html = '<a id="link" href="/safe">Link</a>'
    patch = SetAttr(selector="#link", name="href", value="javascript:steal()")
    res = apply_patch(html, patch)
    assert not res.ok
    assert "forbidden" in res.error.lower()


def test_reject_long_attribute_value_or_html_brackets():
    html = '<img id="pic" src="test.jpg">'
    patch = SetAttr(selector="#pic", name="alt", value="<script>alert(1)</script>")
    res = apply_patch(html, patch)
    assert not res.ok

    long_val = "a" * 161
    patch2 = SetAttr(selector="#pic", name="alt", value=long_val)
    res2 = apply_patch(html, patch2)
    assert not res2.ok


def test_reject_invalid_tabindex():
    html = '<div id="item">Focus</div>'
    patch = SetAttr(selector="#item", name="tabindex", value="5")
    res = apply_patch(html, patch)
    assert not res.ok
    assert "tabindex" in res.error.lower()


def test_reject_css_injection_attempts():
    html = '<p id="p1">Text</p>'
    # url() attempt
    patch1 = AddCss(selector="#p1", property="color", value="url('http://evil.com')")
    res1 = apply_patch(html, patch1)
    assert not res1.ok

    # Semicolon injection
    patch2 = AddCss(selector="#p1", property="color", value="#fff; background: red")
    res2 = apply_patch(html, patch2)
    assert not res2.ok

    # Expression injection
    patch3 = AddCss(selector="#p1", property="color", value="expression(alert(1))")
    res3 = apply_patch(html, patch3)
    assert not res3.ok


def test_reject_ambiguous_or_missing_selector():
    html = '<div><p class="desc">1</p><p class="desc">2</p></div>'
    # Ambiguous selector
    patch1 = SetText(selector="p.desc", value="Unique text")
    res1 = apply_patch(html, patch1)
    assert not res1.ok
    assert "matched 2 elements" in res1.error

    # Missing selector
    patch2 = SetText(selector="#does-not-exist", value="Missing")
    res2 = apply_patch(html, patch2)
    assert not res2.ok
    assert "matched 0 elements" in res2.error


def test_reject_set_text_with_svg_children():
    html = '<button id="btn"><svg></svg></button>'
    patch = SetText(selector="#btn", value="New Text")
    res = apply_patch(html, patch)
    assert not res.ok
    assert "child elements" in res.error.lower()


def test_dry_run_does_not_mutate():
    html = '<h4 id="t">Title</h4>'
    patch = ChangeTag(selector="#t", new_tag="h2")
    res = dry_run(html, patch)
    assert res.ok
    assert "<h2" in res.html_after
    # Original html unchanged
    assert "<h4" in html
