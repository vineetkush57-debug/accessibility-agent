"""Tests for element extraction in backend/extract.py."""

from bs4 import BeautifulSoup

from backend.extract import extract_page_semantics, generate_unique_selector


def test_unique_selector_generation():
    html = """
    <html>
      <body>
        <div id="main">
          <h1>Welcome</h1>
          <p class="intro">Intro paragraph</p>
          <div class="gallery">
            <img src="img1.jpg" alt="pic 1">
            <img src="img2.jpg" alt="pic 2">
          </div>
          <button id="submit-btn">Submit</button>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")

    btn = soup.select_one("#submit-btn")
    assert btn is not None
    sel_btn = generate_unique_selector(btn, soup)
    assert sel_btn == "#submit-btn"
    assert len(soup.select(sel_btn)) == 1

    imgs = soup.select("img")
    assert len(imgs) == 2
    sel_img1 = generate_unique_selector(imgs[0], soup)
    sel_img2 = generate_unique_selector(imgs[1], soup)
    assert sel_img1 != sel_img2
    assert len(soup.select(sel_img1)) == 1
    assert len(soup.select(sel_img2)) == 1


def test_extract_page_semantics_structure():
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Sunrise College - Admissions</title></head>
      <body>
        <h1>Admissions Portal</h1>
        <img class="hero" src="/assets/hero.jpg" alt="image1.jpg">
        <a href="/apply">Click here</a>
        <form>
          <input type="email" id="email" placeholder="Your email">
        </form>
        <button class="menu-toggle"><svg></svg></button>
      </body>
    </html>
    """
    data = extract_page_semantics(html)
    assert data["title"] == "Sunrise College - Admissions"
    assert data["lang"] == "en"

    # Images
    assert len(data["images"]) == 1
    assert data["images"][0]["src_file"] == "hero.jpg"
    assert data["images"][0]["alt"] == "image1.jpg"

    # Links
    assert len(data["links"]) == 1
    assert data["links"][0]["text"] == "Click here"
    assert data["links"][0]["href"] == "/apply"

    # Headings
    assert len(data["headings"]) == 1
    assert data["headings"][0]["level"] == 1
    assert data["headings"][0]["text"] == "Admissions Portal"

    # Fields
    assert len(data["fields"]) == 1
    assert data["fields"][0]["type"] == "email"
    assert data["fields"][0]["placeholder"] == "Your email"

    # Buttons
    assert len(data["buttons"]) == 1
    assert data["buttons"][0]["has_svg"] is True
