# Custom Web Scraper

A desktop GUI for pulling elements off a live web page without writing a
scraping script for each new site. You type a URL, pick a locator strategy
(class, ID, name, tag, link text, partial link text, or XPath), type the
locator value, and the tool drives a real Chrome browser to find every
matching element. Results land in a sortable table (tag, text, attributes)
in a separate window, and a status bar tracks what the app is doing at every
step instead of failing silently.

## Why it exists

Most small scraping jobs don't need a script, they need five minutes of
poking at a page to see what's there: "what are all the `<a>` tags with this
class", "what's the text in this XPath". Writing a one-off Python script for
each of these checks gets old. This tool turns that workflow into a GUI: load
a page once, then try locator after locator against it without touching code.

Because it drives an actual Chrome instance through Selenium rather than
parsing raw HTML, it also works on pages that render content with
JavaScript, which a plain HTTP-request-and-parse scraper cannot handle.

## Features

- Load any URL into a real Chrome browser window from inside the GUI.
- Look up elements by seven different Selenium locator strategies: class
  name, ID, name, tag name, link text, partial link text, and XPath.
- Contextual instructions that update based on which locator strategy is
  selected, so you know what format the value field expects.
- Results open in a separate window as a structured, scrollable table
  (`ttk.Treeview`) with one row per matched element, showing its tag name,
  visible text (whitespace-collapsed and truncated to a sane length), and a
  summary of its key attributes (`id`, `class`, `name`, `href`, `src`,
  `type`, `value`). No more reading raw `WebElement` reprs.
- A single status bar reports what is happening at every step: `Loading
  page...`, `Loaded <url>`, `Found N elements`, or a specific error, colored
  by severity, instead of leaving you guessing or reading a blank screen.
- Session history: the URL field and the locator value field are comboboxes
  that remember up to 10 recently used entries each, so re-testing a
  locator against a page you already loaded is one click, not retyping.
- "Highlight in Browser" button: after a lookup finds elements, this runs a
  small `execute_script` snippet against each live `WebElement` to outline
  it in the actual Chrome window and scroll it into view, so you can see
  exactly what matched without switching to view-source.

## Architecture

Two layers in one file, split by `if __name__ == "__main__":`:

- **Selenium layer** (`build_driver`, `load_html`, the seven
  `get_element_by_*` functions): owns the Chrome `webdriver` instance,
  navigates to the requested URL, and waits (`WebDriverWait`, 10s timeout)
  for the page and then the target locator to appear before reading
  elements. This is what actually touches the network and the DOM, and it
  is unchanged from the original version aside from routing its feedback
  messages through the shared `set_status` helper instead of a bare label.
- **Tkinter layer** (`build_ui` and everything it wires up): builds the
  window, binds the URL entry, locator dropdown, and buttons to the
  Selenium layer's functions, and renders results in a `Toplevel` window
  containing a `ttk.Treeview`. `build_ui` is a standalone function (not
  inline under the `__main__` guard) specifically so it can be constructed
  and driven in a test against a fake driver without starting Chrome.
- **Pure formatting layer** (`summarize_element`, `build_result_rows`):
  takes a list of `WebElement`-like objects and returns plain tuples
  (index, tag, text, attributes) for the Treeview. It only calls read-only
  methods on whatever is passed in and swallows per-attribute failures
  (e.g. a stale element reference), so it has no dependency on a live
  driver and is unit-testable with fake objects.

State is shared through module-level globals: `driver` (the live Selenium
session), `is_request_loaded` (guards against querying elements before a
page has loaded), `last_elements` (the most recent match list, reused by the
highlight button), and the Tkinter widgets themselves (read directly by the
callback functions, since this is a single-window script, not a
class-based app).

## Setup

Requires Python 3.9+, a Chrome (or Chromium) install, and network access the
first time you run it so Selenium Manager can fetch a matching chromedriver.

```bash
python3 -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

tkinter ships with the standard CPython install on Windows and macOS. On
Debian/Ubuntu Linux you may need `sudo apt install python3-tk` if it isn't
already present.

Optional environment variables (see `.env.example`):

- `CHROMEDRIVER_PATH`: point at a specific chromedriver binary. Leave unset
  and Selenium Manager (bundled with selenium 4.6+) resolves and downloads
  the right driver for your installed Chrome version automatically.
- `SCRAPER_HEADLESS`: set to `1` to run Chrome without a visible window.

## Usage

```bash
python main.py
```

1. Enter a URL in the "1. Load a page" panel and click "Request". The tool
   opens the page in Chrome and waits for `<html>` and `<body>` to be
   present. The status bar shows `Loading page...` then `Loaded <url>`, or
   an error if the URL is invalid or the page times out. The URL is
   remembered in the field's dropdown history for next time.
2. Pick a locator strategy from the "Locate by" dropdown in the "2. Find
   elements" panel. The instructions label below it updates to tell you
   what format to type.
3. Enter the class name / ID / XPath / etc. and click "Get Elements". A new
   window opens with a table of every matching element (tag, text,
   attributes). The status bar reports `Found N elements`, and the value is
   added to that field's history too.
4. Click "Highlight in Browser" to outline every matched element in the live
   Chrome window and scroll to it, useful for confirming a locator matched
   the element you actually meant.

## Challenges

**Matching Selenium's strict locators instead of soup-style CSS selectors.**
The project's first working version (still visible as `temp.py` /
`temp1.py` in the source history before this rewrite) used `requests` and
BeautifulSoup with CSS selectors like `.classname` or `#id`, so a bad
selector only raised a `SelectorSyntaxError` that was easy to catch.
Switching to Selenium's `By.CLASS_NAME` / `By.ID` / `By.XPATH` locators for
real browser automation meant a nonexistent match doesn't raise a parse
error at all, it just times out. The fix was wrapping every lookup in
`WebDriverWait(driver, 10).until(...)` and catching `TimeoutException`
specifically, so a missing element surfaces a plain "please enter a valid
X" message instead of the GUI hanging or crashing.

**JavaScript-rendered pages breaking a plain HTTP scraper.** The
requests+BeautifulSoup draft only ever saw the initial HTML response, so
any page that injects content client-side came back empty. Moving to a real
Chrome instance via Selenium fixed this at the cost of needing a browser
and driver installed, which is why the app opens an actual browser window
rather than staying invisible.

**One global driver shared across every locator function.** Every
`get_element_by_*` function reads the same module-level `driver` and
`is_request_loaded` flag rather than taking them as arguments. This was the
simplest way to wire seven near-identical lookup functions to one Tkinter
callback dispatch table, but it means none of them can be unit-tested
without the whole window and driver, and it would break instantly if the
app ever needed to scrape two pages side by side.

**Chrome path portability.** The original `main.py` pointed at a hardcoded
`C:\Development\chromedriver.exe`, which only worked on the original
author's Windows machine. This version resolves the driver through
Selenium Manager by default (falling back to an explicit path via
`CHROMEDRIVER_PATH` if you set one), so the same code runs on Linux, macOS,
or Windows without editing a path in source.

**Distinguishing "no page loaded yet" from "locator found nothing."** Every
lookup function checks `is_request_loaded` first and returns `(None, None)`
with its own error message if no page has been requested, before even
attempting the Selenium query. Without that guard, clicking "Get Elements"
before "Request" would throw on an uninitialized `driver.find_elements`
call instead of showing a helpful message.

**Turning a list of `WebElement` objects into a table without touching a
live driver in tests.** The results view needed one row per element with
tag, text, and attributes, but `WebElement.text` and `.get_attribute()` both
throw if the element reference has gone stale (e.g. the page re-rendered
between the lookup and the render). `summarize_element` wraps every
individual field access in a small `_safe_call` helper that swallows
exceptions and falls back to an empty value, so one bad attribute lookup
doesn't blank out the whole row, and the function's only dependency is
duck-typed attribute access, which made it possible to unit-test with plain
fake objects instead of a real Selenium session.

## What I learned

- `WebDriverWait` plus `expected_conditions` is the right tool for "did this
  show up yet" on a real browser; polling or `time.sleep` guesses would
  either be too slow or too flaky against variable page load times.
- CSS-selector-style scraping (BeautifulSoup) and locator-style scraping
  (Selenium's `By.*`) are not drop-in replacements for each other. Switching
  backends meant rewriting every lookup function's error handling, not just
  swapping the HTTP call for a browser call.
- Selenium Manager (selenium 4.6+) removes almost all of the historical pain
  of matching a chromedriver version to a Chrome version by hand. The
  original hardcoded driver path in this project predates that and was
  the single biggest portability problem in the codebase.
- Separating "build the window" (`build_ui`) from "run the window"
  (`root.mainloop()`) turns a script that could only ever be smoke-tested by
  eye into something a test can construct, drive through fake callbacks, and
  tear down, which is what made testing the new Treeview and status bar
  possible without a live browser.

## What I'd do differently

- Pull the Selenium logic out of module-level globals and into a small
  class (or at least pass `driver` as an argument) so the locator functions
  are testable without booting a browser and a Tkinter window. The seven
  `get_element_by_*` functions are now called through a `LOCATOR_DISPATCH`
  dict instead of a long `if`/`elif` chain, but they still each read the
  same module-level `driver` and duplicate the same
  `is_request_loaded`/`WebDriverWait`/`TimeoutException` shape, so a bug fix
  in one still has to be copied to the other six by hand.
- Persist the URL/locator history to disk (even a small JSON file) instead
  of an in-memory list, since right now it resets every time the app
  restarts.
- Add a way to export the results table (CSV or copy-to-clipboard) instead
  of only viewing it, since pulling attributes out for use elsewhere is a
  common reason to reach for a tool like this.

## What was verified here

This is a GUI application that drives a real Chrome browser, so an
end-to-end run needs a display and a live target site. In this sandbox:

- **Verified:** `main.py` compiles cleanly (`python -m py_compile main.py`).
- **Verified:** the pure result-formatting functions (`summarize_element`,
  `build_result_rows`) with a standalone unit test suite using fake
  duck-typed element objects (no Selenium/browser involved), covering
  normal elements, long text truncation, whitespace collapsing, missing
  attributes, and a simulated stale-element exception on every field. All 7
  cases pass; see `Test plan` below for the exact command and output.
- **Verified:** the full Tkinter window, including the new panels, the
  history comboboxes, the status bar, and the disabled-until-found
  "Highlight in Browser" button, construct without exception against a live
  X display (`DISPLAY=:0`). The test then drives `load_html`,
  `on_get_elements_click`, and `highlight_in_browser` against a fake driver
  that returns fake elements and records `execute_script` calls, confirming
  the status bar text updates correctly at each stage, the results
  `Toplevel`/`Treeview` opens and populates, and history comboboxes capture
  the entered values. `Tk.mainloop` is never called in the test; widgets are
  driven directly and the window is destroyed at the end.
- **Not verified end to end:** a live Chrome session driving a real page,
  and the "Highlight in Browser" JavaScript against a real DOM. This
  sandbox has no outbound network access for Selenium Manager to download a
  matching chromedriver, so an actual `driver.get(url)` call against a real
  site was not exercised here. The Selenium API calls used
  (`webdriver.Chrome`, `WebDriverWait`, `By.*`, `find_elements`,
  `execute_script`) are standard, stable selenium 4.x API and match the
  library's documented usage; run it locally with Chrome installed to
  confirm a live scrape and highlight.
