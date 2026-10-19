import json

from freight.customer import prepared_by_line
from freight.preparers import load_preparers

CASEY = {
    "name": "Casey Ng",
    "title": "Account Executive",
    "email": "casey.ng@example.com",
    "phone": "",
}
RILEY = {
    "name": "Riley Chen",
    "title": "Senior Account Executive",
    "email": "riley.chen@example.com",
    "phone": "(501) 555-0199",
}


def test_roster_is_sorted_by_name(tmp_path):
    roster, source = load_preparers([RILEY, CASEY, {"name": "  ", "title": "Skip"}], tmp_path / "absent.json")
    assert source == "secrets"
    assert [rep["name"] for rep in roster] == ["Casey Ng", "Riley Chen"]
    assert roster[0]["phone"] == ""
    assert roster[1]["phone"] == "(501) 555-0199"


def test_missing_phone_is_left_off_the_prepared_by_line():
    roster, _source = load_preparers([{"name": "Casey Ng", "title": "Account Executive", "email": "casey.ng@example.com"}])
    rep = roster[0]
    assert rep["phone"] == ""
    line = prepared_by_line(rep["name"], rep["title"], rep["email"], rep["phone"])
    assert line == "Prepared by Casey Ng, Account Executive, EasyPost · casey.ng@example.com"
    with_phone = prepared_by_line(RILEY["name"], RILEY["title"], RILEY["email"], RILEY["phone"])
    assert with_phone.endswith("(501) 555-0199")
    assert "·  ·" not in line
    assert "·  ·" not in with_phone


def test_json_file_is_the_fallback(tmp_path):
    path = tmp_path / "preparers.json"
    path.write_text(json.dumps([RILEY, CASEY]), encoding="utf-8")
    roster, source = load_preparers(None, path)
    assert source == "file"
    assert [rep["name"] for rep in roster] == ["Casey Ng", "Riley Chen"]


def test_secrets_win_over_the_file(tmp_path):
    path = tmp_path / "preparers.json"
    path.write_text(json.dumps([RILEY]), encoding="utf-8")
    roster, source = load_preparers([CASEY], path)
    assert source == "secrets"
    assert [rep["name"] for rep in roster] == ["Casey Ng"]


def test_missing_roster_is_empty(tmp_path):
    roster, source = load_preparers(None, tmp_path / "preparers.json")
    assert roster == []
    assert source == ""
    broken = tmp_path / "preparers.json"
    broken.write_text("{not json", encoding="utf-8")
    roster, source = load_preparers(None, broken)
    assert roster == []
    assert source == ""
    roster, source = load_preparers("Casey Ng", broken)
    assert roster == []
    assert source == ""
