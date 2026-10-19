import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from freight.customer import build_customer_quote, prepared_by_line
from freight.pdf_quote import render_customer_pdf
from freight.preparers import ADD_PREPARER, DEFAULT_PATH, apply_preparer_choice, load_preparers, preparer_id, preparer_options

DAWSON_TITLE = "Director of Supply Chain Solutions and Partnerships"

SHIPMENT = {
    "origin_zip_code": "72205",
    "origin_city": "Little Rock",
    "origin_state": "AR",
    "destination_zip_code": "60606",
    "destination_city": "Chicago",
    "destination_state": "IL",
    "pickup_date": "2026-10-20",
    "items": [
        {
            "freight_class": "70",
            "packaging_type": "Pallet",
            "units": 1,
            "total_weight": 500,
            "length": 48,
            "width": 40,
            "height": 48,
        }
    ],
    "accessorials": [],
}


def test_committed_roster_is_sorted_and_has_no_phone():
    roster = load_preparers()
    assert len(roster) == 19
    names = [rep["name"] for rep in roster]
    assert names == sorted(names, key=str.casefold)
    assert all(set(rep) == {"name", "title", "email"} for rep in roster)
    assert all(rep["email"].endswith("@easypost.com") for rep in roster)
    dawson = next(rep for rep in roster if rep["name"] == "Dawson Lamb")
    assert dawson["title"] == DAWSON_TITLE
    assert dawson["email"] == "dlamb@easypost.com"


def test_missing_or_empty_roster_is_empty(tmp_path):
    assert load_preparers(tmp_path / "missing.json") == []
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert load_preparers(empty) == []
    blank = tmp_path / "blank.json"
    blank.write_text('[{"name": "  ", "title": "Skip", "email": "skip@easypost.com"}]', encoding="utf-8")
    assert load_preparers(blank) == []
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert load_preparers(broken) == []
    assert load_preparers(tmp_path) == []


def test_file_roster_drops_phone_and_sorts(tmp_path):
    path = tmp_path / "preparers.json"
    path.write_text(
        json.dumps(
            [
                {"name": "Riley Chen", "title": "Account Executive", "email": "riley@easypost.com", "phone": "(501) 555-0199"},
                {"name": "Casey Ng", "title": "Account Executive", "email": "casey@easypost.com"},
            ]
        ),
        encoding="utf-8",
    )
    roster = load_preparers(path)
    assert [rep["name"] for rep in roster] == ["Casey Ng", "Riley Chen"]
    assert all("phone" not in rep for rep in roster)


def test_add_a_new_person_is_manual_and_does_not_change_the_roster():
    roster = load_preparers()
    original = Path(DEFAULT_PATH).read_bytes()
    options = preparer_options(roster)
    assert options[0] == ("", "Select your name")
    assert options[-1] == (ADD_PREPARER, "+ Add a new person")
    assert options[-2][0] == preparer_id(roster[-1])
    custom = {"name": "Alex Rivera", "title": "Account Executive", "email": "arivera@easypost.com", "phone": "(501) 555-0100"}
    applied = apply_preparer_choice(ADD_PREPARER, roster, custom)
    assert applied == {"name": "Alex Rivera", "title": "Account Executive", "email": "arivera@easypost.com"}
    assert "phone" not in applied
    assert Path(DEFAULT_PATH).read_bytes() == original
    assert all(rep["name"] != "Alex Rivera" for rep in load_preparers())
    dawson = next(rep for rep in roster if rep["name"] == "Dawson Lamb")
    from_roster = apply_preparer_choice(preparer_id(dawson), roster, custom)
    assert from_roster["name"] == "Dawson Lamb"
    assert from_roster["email"] == "dlamb@easypost.com"
    line = prepared_by_line(applied["name"], applied["title"], applied["email"])
    assert line == "Prepared by Alex Rivera, Account Executive, EasyPost · arivera@easypost.com"
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "preparer_name": applied["name"],
            "preparer_title": applied["title"],
            "preparer_email": applied["email"],
            "shipment": SHIPMENT,
            "options": [{"carrier_name": "Carrier", "customer_total": 10, "charges": []}],
        }
    )
    reader = PdfReader(BytesIO(render_customer_pdf(document)))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert line in text
    assert "phone" not in text.lower()
    assert "(501)" not in text


def test_pdf_prepared_by_line_shows_name_title_and_email():
    line = prepared_by_line("Dawson Lamb", DAWSON_TITLE, "dlamb@easypost.com")
    assert line == f"Prepared by Dawson Lamb, {DAWSON_TITLE}, EasyPost · dlamb@easypost.com"
    document = build_customer_quote(
        {
            "customer_name": "Alex Chen",
            "company": "Northwind Goods",
            "quote_date": "2026-10-19",
            "preparer_name": "Dawson Lamb",
            "preparer_title": DAWSON_TITLE,
            "preparer_email": "dlamb@easypost.com",
            "shipment": SHIPMENT,
            "options": [{"carrier_name": "Carrier", "customer_total": 10, "charges": []}],
        }
    )
    assert document["prepared_by"] == line
    reader = PdfReader(BytesIO(render_customer_pdf(document)))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert line in text
    assert "phone" not in text.lower()
    assert "(501)" not in text
