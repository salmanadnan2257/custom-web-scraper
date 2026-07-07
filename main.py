import os

import tkinter as tk
from tkinter import ttk

from selenium import webdriver
from selenium.common import TimeoutException, InvalidArgumentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

is_request_loaded = False

# Elements found by the most recent locator lookup. Kept around so the
# "Highlight in Browser" button can re-use them without re-querying the page.
last_elements = []

# ---------------------------------------------------------------------------
# Colors / style constants (presentation only, no scraping logic below uses
# these directly)
# ---------------------------------------------------------------------------
BG_COLOR = "#1E1B2E"
PANEL_COLOR = "#272340"
ACCENT_COLOR = "#B799FF"
ACCENT_HOVER = "#ACBCFF"
TEXT_COLOR = "#EDEBFA"
MUTED_COLOR = "#9C97BF"
FIELD_BG = "#332E4E"

STATUS_COLORS = {
    "info": "#ACBCFF",
    "success": "#7CE0B8",
    "error": "#FF8FA3",
}


# ---------------------------------------------------------------------------
# Pure helpers: turn Selenium WebElements into plain display data.
#
# These do not touch the driver, take no globals, and only call read-only
# methods on whatever object is passed in, so they can be unit-tested with a
# fake object that just duck-types tag_name / text / get_attribute.
# ---------------------------------------------------------------------------
ATTRIBUTES_TO_SHOW = ("id", "class", "name", "href", "src", "type", "value")


def _safe_call(fn):
    try:
        return fn()
    except Exception:
        return None


def summarize_element(element, index, text_limit=80):
    """Turn one WebElement (or any duck-typed lookalike) into a plain-data
    row: (index, tag, truncated text, attribute summary).
    """
    tag = _safe_call(lambda: element.tag_name) or "?"

    text = _safe_call(lambda: element.text) or ""
    text = " ".join(text.split())
    if len(text) > text_limit:
        text = text[: text_limit - 1] + "…"

    attr_parts = []
    for attr in ATTRIBUTES_TO_SHOW:
        value = _safe_call(lambda a=attr: element.get_attribute(a))
        if value:
            attr_parts.append(f"{attr}={value}")
    attributes = ", ".join(attr_parts)

    return index, tag, text, attributes


def build_result_rows(elements, text_limit=80):
    """Map a list of WebElements to display rows for the results table."""
    return [summarize_element(el, i + 1, text_limit=text_limit) for i, el in enumerate(elements)]


def set_status(message, kind="info"):
    status_bar.config(text=message, foreground=STATUS_COLORS.get(kind, STATUS_COLORS["info"]))


def add_to_history(combobox, value):
    """Push a value to the front of a Combobox's dropdown history, capped at
    10 entries and de-duplicated, without disturbing the current text.
    """
    if not value:
        return
    values = list(combobox["values"])
    if value in values:
        values.remove(value)
    values.insert(0, value)
    combobox["values"] = values[:10]


def on_enter_button(e):
    e.widget["background"] = ACCENT_HOVER


def on_leave_button(e):
    e.widget["background"] = ACCENT_COLOR


def dropdown_var_detect(*args):
    if "instructions" not in globals():
        # Fires once when the OptionMenu sets its initial value, before the
        # instructions label further down in build_ui() exists yet.
        return
    value = dropdown_var.get()
    hints = {
        "Class": "Enter the class name of the element you want to find",
        "ID": "Enter the ID of the element you want to find",
        "Partial Link Text": "Enter the partial link text of the element you want to find",
        "Link Text": "Enter the link text of the element you want to find",
        "Name": "Enter the name of the element you want to find",
        "Tag Name": "Enter the tag name of the element you want to find",
        "XPath": "Enter the XPath of the element you want to find",
    }
    instructions.config(text=hints.get(value, "Pick a locator strategy above"))


def load_html():
    global is_request_loaded
    url = request_url_entry.get().strip()
    set_status("Loading page...", "info")
    root.update_idletasks()
    try:
        driver.get(url)
        is_request_loaded = True
    except InvalidArgumentException:
        set_status("Please enter a valid URL", "error")
        return

    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.CSS_SELECTOR, "html")))
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.CSS_SELECTOR, "body")))
    except TimeoutException:
        set_status("Network error: the page did not load in time", "error")
        return

    add_to_history(request_url_entry, url)
    set_status(f"Loaded {url}", "success")


def get_element_by_class_name(class_name):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.CLASS_NAME, class_name)))
        value = driver.find_elements(By.CLASS_NAME, class_name)
    except TimeoutException:
        set_status("Please enter a valid class name", "error")
        return None, None
    return True, value


def get_element_by_id(id_element):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.ID, id_element)))
        value = driver.find_elements(By.ID, id_element)
    except TimeoutException:
        set_status("Please enter a valid id", "error")
        return None, None
    return True, value


def get_element_by_partial_link_text(partial_link_text):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.PARTIAL_LINK_TEXT, partial_link_text)))
        value = driver.find_elements(By.PARTIAL_LINK_TEXT, partial_link_text)
    except TimeoutException:
        set_status("Please enter a valid partial link text", "error")
        return None, None
    return True, value


def get_element_by_link_text(link_text):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.LINK_TEXT, link_text)))
        value = driver.find_elements(By.LINK_TEXT, link_text)
    except TimeoutException:
        set_status("Please enter a valid link text", "error")
        return None, None
    return True, value


def get_element_by_tag_name(tag_name):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.TAG_NAME, tag_name)))
        value = driver.find_elements(By.TAG_NAME, tag_name)
    except TimeoutException:
        set_status("Please enter a valid tag name", "error")
        return None, None
    return True, value


def get_element_by_xpath(xpath):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.XPATH, xpath)))
        value = driver.find_elements(By.XPATH, xpath)
    except TimeoutException:
        set_status("Please enter a valid xpath", "error")
        return None, None
    return True, value


def get_element_by_name(name):
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return None, None
    try:
        WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.NAME, name)))
        value = driver.find_elements(By.NAME, name)
    except TimeoutException:
        set_status("Please enter a valid name", "error")
        return None, None
    return True, value


LOCATOR_DISPATCH = {
    "Class": get_element_by_class_name,
    "ID": get_element_by_id,
    "Partial Link Text": get_element_by_partial_link_text,
    "Link Text": get_element_by_link_text,
    "Name": get_element_by_name,
    "Tag Name": get_element_by_tag_name,
    "XPath": get_element_by_xpath,
}


def on_get_elements_click():
    global is_request_loaded
    if not is_request_loaded:
        set_status("Please request a URL first", "error")
        return

    locator_type = dropdown_var.get()
    lookup = LOCATOR_DISPATCH.get(locator_type)
    if lookup is None:
        set_status("Pick a locator strategy first", "error")
        return

    locator_value = get_element_by_entry.get().strip()
    condition, data = lookup(locator_value)
    if not condition:
        return

    add_to_history(get_element_by_entry, locator_value)
    count = len(data)
    set_status(f"Found {count} element{'s' if count != 1 else ''}", "success" if count else "info")
    highlight_button.config(state="normal" if count else "disabled")
    show_data(data)


def highlight_in_browser():
    if not last_elements:
        set_status("No elements to highlight yet", "error")
        return
    highlighted = 0
    for element in last_elements:
        try:
            driver.execute_script(
                "arguments[0].style.outline='3px solid #ff3b81';"
                "arguments[0].style.outlineOffset='2px';"
                "arguments[0].scrollIntoView({block: 'center'});",
                element,
            )
            highlighted += 1
        except Exception:
            continue
    if highlighted:
        set_status(f"Highlighted {highlighted} element(s) in the browser window", "success")
    else:
        set_status("Could not highlight those elements (page may have changed)", "error")


def show_data(data_to_show):
    global last_elements
    last_elements = list(data_to_show)

    rows = build_result_rows(data_to_show)

    data_window = tk.Toplevel(root)
    data_window.title(f"Results ({len(rows)} element{'s' if len(rows) != 1 else ''})")
    data_window.geometry("880x480")
    data_window.minsize(640, 320)
    data_window.configure(bg=BG_COLOR)

    header = ttk.Label(
        data_window,
        text=f"Found {len(rows)} matching element(s)",
        font=("Arial", 16, "bold"),
        background=BG_COLOR,
        foreground=ACCENT_COLOR,
    )
    header.pack(anchor="w", padx=18, pady=(16, 8))

    tree_frame = ttk.Frame(data_window)
    tree_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
    tree_frame.rowconfigure(0, weight=1)
    tree_frame.columnconfigure(0, weight=1)

    columns = ("index", "tag", "text", "attributes")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("index", text="#")
    tree.heading("tag", text="Tag")
    tree.heading("text", text="Text")
    tree.heading("attributes", text="Attributes")
    tree.column("index", width=40, anchor="center", stretch=False)
    tree.column("tag", width=90, anchor="w", stretch=False)
    tree.column("text", width=310, anchor="w")
    tree.column("attributes", width=360, anchor="w")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    for row in rows:
        tree.insert("", tk.END, values=row)

    if not rows:
        ttk.Label(
            data_window,
            text="No elements matched this locator.",
            background=BG_COLOR,
            foreground=MUTED_COLOR,
        ).pack(pady=(0, 12))


def build_driver():
    """Start a Chrome webdriver.

    CHROMEDRIVER_PATH lets you point at a specific chromedriver binary. If it
    is not set, Selenium Manager (bundled with selenium >= 4.6) resolves and
    downloads a matching driver automatically.
    """
    chrome_options = Options()
    if os.environ.get("SCRAPER_HEADLESS", "").lower() in ("1", "true", "yes"):
        chrome_options.add_argument("--headless=new")

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    service = Service(chromedriver_path) if chromedriver_path else Service()

    new_driver = webdriver.Chrome(service=service, options=chrome_options)
    new_driver.maximize_window()
    return new_driver


def build_ui():
    """Construct every widget. Split out from __main__ so tests can build the
    window against a fake/mock driver without starting Chrome.
    """
    global root, title, request_url_entry, dropdown_var, get_element_by_entry
    global get_element_by_dropdown, instructions, status_bar, highlight_button

    root = tk.Tk()
    root.title("Custom Web Scraper")
    root.geometry("960x680")
    root.minsize(820, 600)
    root.configure(bg=BG_COLOR)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TFrame", background=BG_COLOR)
    style.configure("Panel.TFrame", background=PANEL_COLOR)
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
    style.configure("Panel.TLabel", background=PANEL_COLOR, foreground=TEXT_COLOR)
    style.configure("Muted.TLabel", background=PANEL_COLOR, foreground=MUTED_COLOR, font=("Arial", 11))
    style.configure("Heading.TLabel", background=BG_COLOR, foreground=ACCENT_COLOR, font=("Arial", 24, "bold"))
    style.configure("Section.TLabel", background=PANEL_COLOR, foreground=ACCENT_COLOR, font=("Arial", 13, "bold"))
    style.configure("TCombobox", fieldbackground=FIELD_BG, background=FIELD_BG, foreground=TEXT_COLOR)
    style.configure(
        "Custom.TMenubutton",
        font=("Arial", 12),
        background=ACCENT_COLOR,
        foreground=BG_COLOR,
    )
    style.map(
        "Custom.TMenubutton",
        background=[("active", ACCENT_HOVER), ("!active", ACCENT_COLOR)],
        foreground=[("active", BG_COLOR), ("!active", BG_COLOR)],
    )

    # ---- Header -----------------------------------------------------
    header_frame = ttk.Frame(root, padding=(20, 16, 20, 8))
    header_frame.pack(fill="x")
    ttk.Label(header_frame, text="Custom Web Scraper", style="Heading.TLabel").pack(anchor="w")
    ttk.Label(
        header_frame,
        text="Drive a real Chrome session, then probe it with locator strategies.",
        style="TLabel",
        foreground=MUTED_COLOR,
    ).pack(anchor="w", pady=(2, 0))

    body = ttk.Frame(root, padding=(20, 4, 20, 4))
    body.pack(fill="both", expand=True)

    # ---- URL panel ----------------------------------------------------
    url_panel = ttk.Frame(body, style="Panel.TFrame", padding=16)
    url_panel.pack(fill="x", pady=(0, 14))
    ttk.Label(url_panel, text="1. Load a page", style="Section.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
    )

    request_url_entry = ttk.Combobox(url_panel, font=("Arial", 13), foreground=TEXT_COLOR)
    request_url_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), ipady=4)
    request_url_entry.set("https://")

    request_button = tk.Button(
        url_panel,
        text="Request",
        font=("Arial", 12, "bold"),
        bg=ACCENT_COLOR,
        fg=BG_COLOR,
        activebackground=ACCENT_HOVER,
        activeforeground=BG_COLOR,
        bd=0,
        padx=18,
        pady=6,
        command=load_html,
    )
    request_button.grid(row=1, column=1, sticky="e")
    request_button.bind("<Enter>", on_enter_button)
    request_button.bind("<Leave>", on_leave_button)

    url_panel.columnconfigure(0, weight=1)

    # ---- Locator panel --------------------------------------------------
    locator_panel = ttk.Frame(body, style="Panel.TFrame", padding=16)
    locator_panel.pack(fill="x", pady=(0, 14))
    ttk.Label(locator_panel, text="2. Find elements", style="Section.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
    )

    ttk.Label(locator_panel, text="Locate by", style="Panel.TLabel").grid(row=1, column=0, sticky="w")
    dropdown_var = tk.StringVar(root)
    dropdown_var.trace("w", dropdown_var_detect)
    get_element_by_dropdown = ttk.OptionMenu(
        locator_panel,
        dropdown_var,
        "Select",
        "Class",
        "ID",
        "Partial Link Text",
        "Link Text",
        "Name",
        "Tag Name",
        "XPath",
        style="Custom.TMenubutton",
    )
    get_element_by_dropdown.grid(row=2, column=0, sticky="w", pady=(4, 10))

    get_element_by_entry = ttk.Combobox(locator_panel, font=("Arial", 13), foreground=TEXT_COLOR)
    get_element_by_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=(4, 10), ipady=4)

    get_elements_button = tk.Button(
        locator_panel,
        text="Get Elements",
        font=("Arial", 12, "bold"),
        bg=ACCENT_COLOR,
        fg=BG_COLOR,
        activebackground=ACCENT_HOVER,
        activeforeground=BG_COLOR,
        bd=0,
        padx=18,
        pady=6,
        command=on_get_elements_click,
    )
    get_elements_button.grid(row=2, column=2, sticky="e", pady=(4, 10))
    get_elements_button.bind("<Enter>", on_enter_button)
    get_elements_button.bind("<Leave>", on_leave_button)

    highlight_button = tk.Button(
        locator_panel,
        text="Highlight in Browser",
        font=("Arial", 11),
        bg=FIELD_BG,
        fg=TEXT_COLOR,
        activebackground=ACCENT_HOVER,
        activeforeground=BG_COLOR,
        bd=0,
        padx=14,
        pady=5,
        state="disabled",
        command=highlight_in_browser,
    )
    highlight_button.grid(row=3, column=2, sticky="e")

    instructions = ttk.Label(
        locator_panel,
        text="Pick a locator strategy above",
        style="Muted.TLabel",
        wraplength=560,
    )
    instructions.grid(row=3, column=0, columnspan=2, sticky="w")

    locator_panel.columnconfigure(1, weight=1)

    # ---- Status bar -----------------------------------------------------
    status_frame = ttk.Frame(root, padding=(20, 4, 20, 16))
    status_frame.pack(fill="x", side="bottom")
    status_bar = ttk.Label(
        status_frame,
        text="Idle. Enter a URL and click Request to begin.",
        font=("Arial", 12),
        foreground=STATUS_COLORS["info"],
        background=BG_COLOR,
    )
    status_bar.pack(anchor="w")

    return root


if __name__ == "__main__":
    driver = build_driver()
    build_ui()
    root.mainloop()
    driver.quit()
