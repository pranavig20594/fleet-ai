"""
Generate messy, realistic synthetic fleet documents as PDFs and .eml emails.
Messiness includes: inconsistent date formats, varied truck labels, OCR artifacts,
missing fields, typos, email reply chains, and mixed casing.
"""
import random
import textwrap
from email.message import EmailMessage
from pathlib import Path
from datetime import date, timedelta
from fpdf import FPDF

TRUCKS = ["84", "22", "31", "47", "09", "115"]
DRIVERS = {
    "84":  "Mike Torres",
    "22":  "Dave Chen",
    "31":  "Sarah Kowalski",
    "47":  "James Wright",
    "09":  "Luis Mendez",
    "115": "Tom Briggs",
}
FUEL_STOPS = [
    ("Flying J Truck Stop",   "3421 I-40 W, Amarillo TX",   "806"),
    ("Loves Travel Stop",     "1200 Hwy 287, Fort Worth TX", "817"),
    ("Pilot Flying J",        "500 I-20 E, Abilene TX",      "325"),
    ("TA Travel Center",      "8900 I-35 N, Waco TX",        "254"),
]
SHOPS = [
    ("Peterbilt of Dallas",       "peterbilt-dallas@dealers.com"),
    ("Interstate Parts & Supply", "invoices@interstateparts.com"),
    ("Cummins Engine Service",    "service@cummins-dfw.com"),
    ("Great Plains Diesel",       "billing@greatplainsdiesel.com"),
]
COMPANY_EMAIL = "dispatch@lonestartucking.com"
COMPANY_NAME  = "LONE STAR TRUCKING LLC"

# ---------------------------------------------------------------------------
# Messiness helpers
# ---------------------------------------------------------------------------

def rdate_obj(year: int = 2024) -> date:
    return date(year, 1, 1) + timedelta(days=random.randint(0, 364))


def messy_date(year: int = 2024) -> str:
    """Return the same date in a randomly chosen real-world format."""
    d = rdate_obj(year)
    fmts = [
        "%Y-%m-%d",          # 2024-03-15
        "%m/%d/%Y",          # 03/15/2024
        "%m/%d/%y",          # 03/15/24
        "%m-%d-%Y",          # 03-15-2024
        "%d %b %Y",          # 15 Mar 2024
        "%b %d, %Y",         # Mar 15, 2024
        "%B %d %Y",          # March 15 2024
        "%-m/%-d/%y",        # 3/15/24
    ]
    try:
        return d.strftime(random.choice(fmts))
    except ValueError:
        return d.strftime("%m/%d/%Y")


def messy_truck(truck: str) -> str:
    """Return the truck number in one of many real-world label styles."""
    return random.choice([
        f"Truck {truck}",
        f"Truck #{truck}",
        f"Unit {truck}",
        f"Unit #{truck}",
        f"Unit# {truck}",
        f"T-{truck}",
        f"T{truck}",
        f"VEH {truck}",
        f"#{truck}",
        truck,
        f"truck no. {truck}",
        f"UNIT {truck}",
        f"vehicle {truck}",
    ])


def messy_amount(amount: float) -> str:
    """Return dollar amount in an inconsistent format."""
    return random.choice([
        f"${amount:.2f}",
        f"$ {amount:.2f}",
        f"{amount:.2f}",
        f"${amount:,.2f}",
        f"USD {amount:.2f}",
        f"{amount:.1f}",          # truncated cents
        f"${round(amount)}",      # rounded to whole dollar
    ])


def messy_driver(name: str) -> str:
    """Return driver name in one of several real-world styles."""
    parts = name.split()
    first, last = parts[0], parts[-1]
    return random.choice([
        name,
        name.upper(),
        name.lower(),
        f"{last}, {first}",
        f"{last.upper()}, {first}",
        f"{first[0]}. {last}",
        f"{first} {last[0]}.",
        last,
    ])


def messy_shop(name: str) -> str:
    """Introduce occasional typos or abbreviations in vendor names."""
    typos = {
        "Peterbilt of Dallas":       ["Peterbilt Dallas", "Peterblt of Dallas", "PB Dallas", "PETERBILT OF DALLAS"],
        "Interstate Parts & Supply": ["Interstate Parts & Suply", "Interstate Parts", "I-State Parts & Supply", "INTERSTATE PARTS"],
        "Cummins Engine Service":    ["Cummins Eng. Service", "Cummins Svc", "CUMMINS ENGINE SVC", "Cummins Engin Service"],
        "Great Plains Diesel":       ["Great Plains Dsl", "Gt Plains Diesel", "GREAT PLAINS DIESEL", "Great Plain Diesel"],
    }
    return random.choice(typos.get(name, [name]))


def ocr_corrupt(text: str) -> str:
    """Randomly introduce OCR-like character substitutions."""
    if random.random() > 0.4:
        return text          # 60% of docs are clean
    subs = {"0": "O", "1": "l", "S": "5", "B": "8", "I": "1", "g": "9"}
    result = []
    for ch in text:
        if ch in subs and random.random() < 0.03:   # 3% chance per char
            result.append(subs[ch])
        else:
            result.append(ch)
    return "".join(result)


def scan_noise(text: str) -> str:
    """Add scanning artifacts: extra blank lines, broken words, stray dashes."""
    if random.random() > 0.3:
        return text
    lines = text.split("\n")
    noisy = []
    for line in lines:
        noisy.append(line)
        if line.strip() and random.random() < 0.08:
            noisy.append("")          # random extra blank line
    return "\n".join(noisy)


def maybe_omit(value: str, probability: float = 0.15) -> str:
    """Randomly blank out a field to simulate missing data."""
    return "" if random.random() < probability else value


def watermark_text() -> str:
    return random.choice(["", "", "", "COPY", "PAID", "DUPLICATE", "VOID"])  # mostly empty


def vin(truck: str) -> str:
    v = f"1XPBD49X{random.randint(1,9)}DF{int(truck):06d}"
    # Sometimes VIN is partial or has a typo
    if random.random() < 0.2:
        v = v[:8] + "..." + v[-6:]
    return v


# ---------------------------------------------------------------------------
# PDF + EML output
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    """Replace Unicode characters unsupported by fpdf2's built-in fonts."""
    return (text
        .replace("—", "--")   # em dash
        .replace("–", "-")    # en dash
        .replace("’", "'")    # right single quote
        .replace("‘", "'")    # left single quote
        .replace("“", '"')    # left double quote
        .replace("”", '"')    # right double quote
        .replace("…", "...")   # ellipsis
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def to_pdf(text: str, path: Path, wm: str = "") -> None:
    text = _ascii_safe(text)
    pdf  = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if wm:
        pdf.set_font("Helvetica", style="B", size=36)
        pdf.set_text_color(210, 210, 210)
        pdf.cell(0, 20, wm, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Courier", size=10)
    max_chars = 95
    for line in text.split("\n"):
        if len(line) > max_chars:
            for chunk in textwrap.wrap(line, width=max_chars) or [""]:
                pdf.multi_cell(0, 5, chunk, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def to_eml(subject: str, from_addr: str, body: str, path: Path) -> None:
    from email.utils import format_datetime
    from datetime import datetime, timezone
    msg = EmailMessage()
    msg["From"]    = from_addr
    msg["To"]      = COMPANY_EMAIL
    msg["Subject"] = subject
    msg["Date"]    = format_datetime(datetime.now(timezone.utc))
    msg.set_content(body)
    path.write_text(msg.as_string())


# ---------------------------------------------------------------------------
# Email thread noise
# ---------------------------------------------------------------------------

def wrap_in_reply_chain(body: str, subject: str, from_addr: str) -> str:
    """Optionally wrap the email body in a realistic reply/forward chain."""
    if random.random() > 0.4:
        return body             # 60% are clean single emails

    quoted = textwrap.indent(body, "> ")
    noise  = random.choice([
        f"Please see below.\n\n{body}\n\n--- Forwarded message ---\nFrom: {from_addr}\nSubject: Fwd: {subject}\n\n{quoted}",
        f"Got it, thanks.\n\nOn {messy_date()}, {from_addr} wrote:\n{quoted}",
        f"Following up on the below.\n\n{body}\n\n-----Original Message-----\nFrom: {from_addr}\nSent: {messy_date()}\n\n{quoted}",
        f"Resending — did you receive this?\n\n{body}",
    ])
    disclaimer = random.choice([
        "",
        "\n\n-- \nThis email and any attachments are confidential.",
        "\n\nCAUTION: This email originated from outside the organization.",
        "\n\nPLEASE NOTE: Our office hours are Mon-Fri 7am-5pm CST.",
    ])
    return noise + disclaimer


def email_signature(shop_name: str, shop_email: str) -> str:
    ext = random.randint(100, 999)
    return random.choice([
        f"\n\nBest,\n{shop_name}\nAccounts Receivable\nTel: (214) {random.randint(200,999)}-{random.randint(1000,9999)} x{ext}\n{shop_email}",
        f"\n\nThank you,\n{shop_name}\n{shop_email}\nPhone: 1-800-{random.randint(100,999)}-{random.randint(1000,9999)}",
        f"\n\n{shop_name.upper()}\nBILLING DEPT | {shop_email}",
        "",
    ])


# ---------------------------------------------------------------------------
# Document generators
# ---------------------------------------------------------------------------

def fuel_receipt(truck: str) -> str:
    driver      = messy_driver(DRIVERS.get(truck, "Unknown"))
    name, addr, area = random.choice(FUEL_STOPS)
    gallons     = random.randint(80, 200)
    ppg         = round(random.uniform(3.80, 4.50), 3)
    total       = round(gallons * ppg, 2)
    label       = maybe_omit(messy_truck(truck))
    trailer     = f"TR-{random.randint(100,999)}" if random.random() > 0.5 else ""
    driver_line = maybe_omit(f"Driver:  {driver}")
    note        = random.choice(["", "", "", "** CUSTOMER COPY **", "DUPLICATE RECEIPT", f"See fleet mgr - {random.choice(['disputed','approved','hold'])}"])

    text = f"""
{random.choice([name, name.upper(), name + " #" + str(random.randint(1,9))])}
{addr}
Tel: ({area}) {random.randint(100,999)}-{random.randint(1000,9999)}

{"FUEL RECEIPT" if random.random() > 0.3 else "SALES RECEIPT / FUEL"}
Date: {messy_date()}
Time: {random.randint(6,22)}:{random.choice(['00','15','30','45'])}

{driver_line}
{"Vehicle: " + label if label else ""}
{"Trailer: " + trailer if trailer else ""}

Fuel Type: {"Diesel" if random.random() > 0.1 else "DEF"}
Gallons:   {gallons:.1f}
Price/Gal: {messy_amount(ppg)}
Amount:    {messy_amount(total)}

Payment: {"Fleet Card" if random.random() > 0.3 else random.choice(["Cash","Check","Credit Card"])}
{"Auth#: " + str(random.randint(100000, 999999)) if random.random() > 0.2 else ""}
{note}
""".strip()

    return ocr_corrupt(scan_noise(text))


def maintenance_receipt(truck: str) -> str:
    shop_name, _ = random.choice(SHOPS)
    display_shop = messy_shop(shop_name)
    services     = random.sample([
        ("Oil & Filter Change",           random.uniform(180, 350)),
        ("Brake Inspection & Adjustment", random.uniform(200, 800)),
        ("Tire Rotation",                 random.uniform(120, 250)),
        ("Coolant System Flush",          random.uniform(150, 300)),
        ("Air Filter Replacement",        random.uniform(80,  200)),
        ("Fuel Filter",                   random.uniform(60,  150)),
        ("DEF System Service",            random.uniform(200, 500)),
        ("Fan Belt Replacement",          random.uniform(300, 600)),
        ("Injector Cleaning",             random.uniform(400, 900)),
    ], k=random.randint(1, 4))
    subtotal = sum(s[1] for s in services)
    tax      = subtotal * 0.0825
    total    = subtotal + tax

    unit_line = maybe_omit(f"Unit: {messy_truck(truck)}", 0.1)
    lines     = f"""REPAIR ORDER — {display_shop}
Work Order #: RO-{random.randint(10000,99999)}
Date: {messy_date()}

{unit_line}
{"Mileage: " + f"{random.randint(250000, 900000):,}" if random.random() > 0.2 else ""}
{"VIN: " + vin(truck) if random.random() > 0.25 else ""}

"""
    for svc_name, amt in services:
        # Occasionally omit line-item price
        if random.random() < 0.1:
            lines += f"  {svc_name:<42}  (see attached)\n"
        else:
            lines += f"  {svc_name:<42} {messy_amount(amt):>10}\n"

    lines += f"""
  Subtotal:                                {messy_amount(subtotal):>10}
  {"Tax (8.25%):" if random.random()>0.2 else "Sales Tax:  "}                             {messy_amount(tax):>10}
  TOTAL DUE:                               {messy_amount(total):>10}

{"Authorized: " + random.choice(["Shop Manager","J. Hernandez","R. Patel","Service Advisor"]) if random.random()>0.1 else ""}
{"PO#: " + str(random.randint(10000,99999)) if random.random()>0.5 else ""}
"""
    return ocr_corrupt(scan_noise(lines.strip()))


def maintenance_email_body(truck: str) -> tuple[str, str, str]:
    shop_name, shop_email = random.choice(SHOPS)
    display_shop          = messy_shop(shop_name)
    services = random.sample([
        ("Oil & Filter Change",           random.uniform(180, 350)),
        ("Brake Inspection & Adjustment", random.uniform(200, 800)),
        ("Tire Rotation",                 random.uniform(120, 250)),
        ("Coolant System Flush",          random.uniform(150, 300)),
        ("Air Filter Replacement",        random.uniform(80,  200)),
        ("DEF System Service",            random.uniform(200, 500)),
    ], k=random.randint(1, 3))
    subtotal = sum(s[1] for s in services)
    tax      = subtotal * 0.0825
    total    = subtotal + tax
    d        = messy_date()
    wo       = f"RO-{random.randint(10000,99999)}"

    subj_variants = [
        f"Invoice {wo} – Unit {truck} Service – {d}",
        f"Re: Work Order {wo} / {messy_truck(truck)}",
        f"[INVOICE] {display_shop} – {d}",
        f"Service Complete – {messy_truck(truck)} – {wo}",
    ]
    subject = random.choice(subj_variants)

    greeting = random.choice([
        f"Hi {COMPANY_NAME},",
        "Hi,",
        "Hello,",
        "To Whom It May Concern,",
        f"Dear Accounts Payable,",
        "",
    ])

    body = f"""{greeting}

Please find {"below" if random.random()>0.3 else "attached"} the invoice for service completed on {messy_truck(truck)}.

Work Order: {wo}
Date: {d}
Unit: {messy_truck(truck)}
{"VIN: " + vin(truck) if random.random()>0.3 else ""}
{"Mileage: " + f"{random.randint(250000,900000):,}" if random.random()>0.4 else ""}

Services Performed:
"""
    for svc_name, amt in services:
        body += f"  - {svc_name}: {messy_amount(amt)}\n"

    body += f"""
Subtotal: {messy_amount(subtotal)}
Tax: {messy_amount(tax)}
{"TOTAL: " if random.random()>0.5 else "Balance Due: "}{messy_amount(total)}

{"Payment due within 30 days." if random.random()>0.3 else "Net 15."}
Please reference {wo} on your payment.
"""
    body += email_signature(display_shop, shop_email)
    body  = wrap_in_reply_chain(body, subject, shop_email)
    return subject, shop_email, body


def fuel_summary_email_body(truck: str) -> tuple[str, str, str]:
    driver  = messy_driver(DRIVERS.get(truck, "Unknown"))
    months  = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
    month   = random.choice(months)
    stops   = random.randint(8, 20)
    gallons = random.randint(1200, 3500)
    total   = round(gallons * random.uniform(3.90, 4.40), 2)

    subj_variants = [
        f"Fuel Card Statement – {messy_truck(truck)} – {month} 2024",
        f"Monthly Fuel Summary / Unit {truck} / {month}",
        f"[STATEMENT] Fleet Fuel – {month} 2024",
        f"Fuel Activity Report – {driver} – {month}",
    ]
    subject = random.choice(subj_variants)

    body = f"""{"To: " + COMPANY_NAME if random.random()>0.4 else ""}
{"Re: Monthly Fuel Summary" if random.random()>0.3 else ""}

{"Driver: " + driver if random.random()>0.2 else ""}
{messy_truck(truck)}
Period: {month} 2024

Summary:
  Total Stops:   {stops}
  Total Gallons: {gallons:.1f} gal
  Total Charged: {messy_amount(total)}
  Avg $/Gal:     {messy_amount(total/gallons)}

{"Note: " + random.choice(["1 disputed transaction on 3/14", "DEF purchases included", "Card #ending 4821 used", ""]) if random.random()>0.5 else ""}

For transaction detail visit the portal or reply to this email.
{"Questions? Call 1-800-" + str(random.randint(200,999)) + "-" + str(random.randint(1000,9999)) if random.random()>0.4 else ""}

Fleet Card Services
{"statements@fleetcardservices.com" if random.random()>0.3 else "no-reply@fuelcardstatements.net"}
"""
    body = wrap_in_reply_chain(body, subject, "statements@fleetcardservices.com")
    return subject, "statements@fleetcardservices.com", body


def registration(truck: str) -> str:
    exp_year = random.choice([2024, 2025])
    plate    = f"TX{random.randint(10000,99999)}"
    makes    = ["Peterbilt", "Kenworth", "Freightliner", "International"]
    text = f"""{"STATE OF TEXAS" if random.random()>0.2 else "TEXAS DMV"}
{"MOTOR VEHICLE REGISTRATION CERTIFICATE" if random.random()>0.3 else "REGISTRATION RECEIPT"}

Unit Number:  {maybe_omit(messy_truck(truck), 0.05)}
Plate:        {plate}
{"VIN:          " + vin(truck) if random.random()>0.15 else ""}
Year:         {random.choice([2018,2019,2020,2021])}
Make:         {random.choice(makes)}
GVWR:         80,000 lbs

Registered Owner: {COMPANY_NAME}
Address: 4500 Industrial Blvd, Dallas TX 75201

Registration Period: {exp_year}-01-01 through {exp_year}-12-31
Fee Paid: {messy_amount(random.randint(800,1800))}
Receipt #: {random.randint(1000000,9999999)}

Issued: {messy_date(exp_year - 1)}
""".strip()
    return ocr_corrupt(scan_noise(text))


def tax_form(truck: str) -> str:
    text = f"""HEAVY VEHICLE USE TAX — FORM 2290
{"Internal Revenue Service" if random.random()>0.2 else "IRS / HVUT"}

Tax Period: {"July 1, 2023" if random.random()>0.2 else "07/01/2023"} – {"June 30, 2024" if random.random()>0.2 else "06/30/2024"}

Taxpayer:  {COMPANY_NAME}
EIN:       75-{random.randint(1000000,9999999)}

  {messy_truck(truck)}
  {"VIN: " + vin(truck) if random.random()>0.15 else ""}
  Taxable Gross Weight: 80,000 lbs

Tax Due:     {messy_amount(550)}
Amount Paid: {messy_amount(550)}
Date Filed:  {messy_date(2023)}

Confirmation: {random.randint(10000000,99999999)}
""".strip()
    return ocr_corrupt(text)


def title_doc(truck: str) -> str:
    makes = ["Peterbilt", "Kenworth", "Freightliner", "International"]
    make  = random.choice(makes)
    yr    = random.choice([2018, 2019, 2020, 2021])
    model = {"Peterbilt": "389", "Kenworth": "T680", "Freightliner": "Cascadia"}.get(make, "LT")
    text  = f"""STATE OF TEXAS
CERTIFICATE OF TITLE — MOTOR VEHICLE

Title Number: {random.randint(10000000,99999999)}

Vehicle:
  Year:  {yr}
  Make:  {make}
  Model: {model}
  {"VIN:   " + vin(truck) if random.random()>0.1 else ""}
  Color: {"White" if random.random()>0.4 else random.choice(["Red","Silver","Black","Blue"])}
  Unit:  {maybe_omit(truck, 0.1)}

Owner: {COMPANY_NAME}
       4500 Industrial Blvd
       Dallas TX 75201

Lienholder: {"None" if random.random()>0.4 else "First National Bank, Dallas TX"}

Issue Date: {messy_date(yr)}
""".strip()
    return ocr_corrupt(scan_noise(text))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    out = Path(__file__).parent.parent / "documents"
    out.mkdir(exist_ok=True)

    count = 0
    for truck in TRUCKS:
        # Fuel receipts → PDFs (some with watermarks)
        for _ in range(random.randint(8, 14)):
            wm = watermark_text()
            to_pdf(fuel_receipt(truck), out / f"fuel_{truck}_{count}.pdf", wm=wm)
            count += 1

        # Maintenance → mix of PDFs and emails
        for _ in range(random.randint(3, 6)):
            if random.random() > 0.45:
                to_pdf(maintenance_receipt(truck), out / f"maint_{truck}_{count}.pdf",
                       wm=watermark_text())
            else:
                subj, frm, body = maintenance_email_body(truck)
                to_eml(subj, frm, body, out / f"maint_{truck}_{count}.eml")
            count += 1

        # Fuel card monthly summaries → emails (1-2 per truck)
        for _ in range(random.randint(1, 2)):
            subj, frm, body = fuel_summary_email_body(truck)
            to_eml(subj, frm, body, out / f"fuel_summary_{truck}_{count}.eml")
            count += 1

        # Official docs → PDFs
        to_pdf(registration(truck), out / f"reg_{truck}_{count}.pdf")
        count += 1
        to_pdf(tax_form(truck),     out / f"tax_{truck}_{count}.pdf")
        count += 1
        to_pdf(title_doc(truck),    out / f"title_{truck}_{count}.pdf")
        count += 1

    print(f"Generated {count} documents → {out}")


if __name__ == "__main__":
    main()
