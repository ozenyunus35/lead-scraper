"""Browser tests for the results page, on desktop Chrome, desktop Safari, iPhone and Android.

The page is served from a temporary folder with fixture data, so the tests do
not depend on a scraper run. Set BASE_URL to test the live site instead.
"""

import functools
import os
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
expect = playwright_api.expect

ROOT = Path(__file__).resolve().parent.parent
PROFILES = {
    "desktop-chrome": ("chromium", {"viewport": {"width": 1280, "height": 800}}),
    "desktop-safari": ("webkit", {"viewport": {"width": 1280, "height": 800}}),
    "iphone": ("webkit", "iPhone 15 Pro"),
    "android": ("chromium", "Pixel 7"),
}


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    if os.environ.get("BASE_URL"):
        yield os.environ["BASE_URL"]
        return
    root = tmp_path_factory.mktemp("site")
    for name in ("index.html", "app.js", "style.css"):
        shutil.copy(ROOT / "site" / name, root / name)
    shutil.copytree(ROOT / "tests" / "fixtures" / "site-data", root / "data")
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SimpleHTTPRequestHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture(scope="session")
def pw():
    with playwright_api.sync_playwright() as p:
        yield p


@pytest.fixture(params=list(PROFILES), scope="session")
def browser_ctx(request, pw):
    engine, options = PROFILES[request.param]
    browser = getattr(pw, engine).launch()
    yield browser, (pw.devices[options] if isinstance(options, str) else options)
    browser.close()


@pytest.fixture
def page(browser_ctx, base_url):
    browser, options = browser_ctx
    context = browser.new_context(**options)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base_url)
    expect(page.locator("#table tbody tr").first).to_be_visible()
    yield page
    context.close()
    assert not errors, errors


def test_shows_pipeline_and_records(page):
    expect(page.get_by_role("heading", level=1)).to_have_text("Business leads")
    pipeline = page.get_by_role("list", name="What the last run did")
    for step in ("Crawl", "Parse", "Clean", "Merge", "Export"):
        expect(pipeline).to_contain_text(step)
    rows = page.locator("#table tbody tr")
    total = rows.count()
    assert total > 20
    expect(page.locator("#count")).to_have_text(f"{total} of {total} records")
    expect(page.get_by_role("link", name="Excel")).to_have_attribute("href", "data/directory.xlsx")
    expect(page.locator(".tag.merged").first).to_be_visible()


def test_filters_narrow_the_table(page):
    page.get_by_label("City").select_option("Oakland")
    rows = page.locator("#table tbody tr")
    assert rows.count() > 0
    for i in range(rows.count()):
        expect(rows.nth(i).locator("td").first).to_contain_text("Oakland")
    page.get_by_label("City").select_option("")
    page.get_by_label("Filter rows").fill("zzzz-no-match")
    expect(page.locator("#note")).to_have_text("No records match these filters.")


def test_breakdown_sets_the_category_filter(page):
    page.locator("#breakdown button").first.click()
    category = page.get_by_label("Category").input_value()
    assert category
    rows = page.locator("#table tbody tr")
    for i in range(rows.count()):
        expect(rows.nth(i).locator("td.cat")).to_contain_text(category)


def test_record_dialog_shows_every_field(page):
    first = page.locator("#table tbody tr").first
    e164 = first.locator("td").nth(2).locator(".sub").inner_text()
    assert e164.startswith("+1")
    first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    for label in ("Phone (E.164)", "Street", "ZIP", "Source page"):
        expect(dialog).to_contain_text(label)
    expect(dialog.locator("code")).to_have_text(e164)
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_be_hidden()


def test_books_dataset_and_theme(page):
    page.get_by_role("tab", name="Books (sandbox)").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Books")
    expect(page.get_by_role("columnheader", name="Price (£)")).to_be_visible()
    page.get_by_label("Rating").select_option("5")
    assert page.locator("#table tbody tr").count() > 0
    dark = page.evaluate("document.documentElement.classList.contains('dark')")
    page.get_by_role("button", name="Switch theme").click()
    page.reload()
    assert page.evaluate("document.documentElement.classList.contains('dark')") is not dark
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
