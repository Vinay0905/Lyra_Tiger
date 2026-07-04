from src.skills.browser.engine import InteractiveElement, PageModel

# Injected in-page: tags each interactive element with a stable data-lyra-ref and
# returns a compact index plus readable main text. Keeping extraction in one JS
# pass avoids chatty round-trips and yields deterministic selectors.
_EXTRACT_JS = r"""
() => {
  const SEL = 'a[href], button, input, textarea, select, [role="button"], [role="link"]';
  const nodes = Array.from(document.querySelectorAll(SEL));
  const elements = [];
  let i = 0;
  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;

    const ref = '@e' + (i++);
    el.setAttribute('data-lyra-ref', ref);

    const role = (el.getAttribute('role')
      || el.tagName.toLowerCase());
    const name = (el.getAttribute('aria-label')
      || el.innerText
      || el.value
      || el.getAttribute('placeholder')
      || el.getAttribute('title')
      || '').trim().slice(0, 120);

    elements.push({ ref, role, name });
    if (i >= 200) break;
  }

  // Readable main text: prefer semantic containers, fall back to body.
  const main = document.querySelector('main, article, [role="main"]') || document.body;
  const text = (main ? main.innerText : '').replace(/\s+\n/g, '\n').trim().slice(0, 6000);

  return {
    url: location.href,
    title: document.title || '',
    main_text: text,
    elements,
  };
}
"""


async def extract_page_model(page) -> PageModel:
    """Run the single-pass extractor against a live Playwright page."""
    try:
        data = await page.evaluate(_EXTRACT_JS)
    except Exception:
        # Page may be mid-navigation; return a minimal model rather than raising.
        try:
            return PageModel(url=page.url, title=await page.title())
        except Exception:
            return PageModel()

    return PageModel(
        url=data.get("url", ""),
        title=data.get("title", ""),
        main_text=data.get("main_text", ""),
        elements=[
            InteractiveElement(
                ref=e.get("ref", ""),
                role=e.get("role", "element"),
                name=e.get("name", ""),
            )
            for e in data.get("elements", [])
        ],
    )
