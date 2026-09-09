from extraction.parse import parse_document, parse_form_text, parse_receipt_text


STARBUCKS = """
STARBUCKS STORE #10208
11302 EUCLID AVENUE
CLEVELAND, OH
TAX INVOICE
DATE: 14/03/2015
LATTE                     4.50
TOTAL                     4.95
CASH                      10.00
CHANGE                    5.05
"""

TONG_SENG = """
SYARIKAT PERNIAGAAN TONG SENG
NO 35 JALAN SAGU 18
TAX INVOICE
DATE 25/12/2018
ITEM A        3.00
ITEM B        6.00
SUBTOTAL      9.00
TOTAL RM 9.00
"""

WRAPPED_COMPANY = """
UNIHAKKA INTERNATIONAL
SDN BHD
12 JALAN ABC
09/01/2019
ROUNDING      0.05
GRAND TOTAL   31.00
"""


def test_starbucks_like_receipt():
    fields = parse_receipt_text(STARBUCKS)
    assert fields.merchant and "STARBUCKS" in fields.merchant.upper()
    assert fields.date == "14/03/2015"
    assert fields.total == "4.95"


def test_prefers_labeled_total_over_subtotal_and_change():
    fields = parse_receipt_text(TONG_SENG)
    assert "TONG SENG" in (fields.merchant or "").upper()
    assert fields.date == "25/12/2018"
    assert fields.total == "9.00"


def test_wrapped_company_and_grand_total():
    fields = parse_receipt_text(WRAPPED_COMPANY)
    assert fields.merchant is not None
    assert "UNIHAKKA" in fields.merchant.upper()
    assert "SDN BHD" in fields.merchant.upper()
    assert fields.date == "09/01/2019"
    assert fields.total == "31.00"


def test_qty_price_is_not_a_date():
    fields = parse_receipt_text("RESTORAN WAN SHENG\n10 2.10\nTOTAL 4.60\n")
    assert fields.date is None
    assert fields.total == "4.60"


def test_change_and_total_labels_are_not_dates():
    fields = parse_receipt_text("SANYU\nCASH 10.00\nCHANGE 1.30\nTOTAL 8.70\n")
    assert fields.date is None
    assert fields.total == "8.70"
    fields = parse_receipt_text("UNIHAKKA\n10 MAY 2018\nTOTAL $10.30\n")
    assert fields.date.upper() == "10 MAY 2018"
    assert fields.total == "10.30"


def test_empty_text():
    fields = parse_receipt_text("")
    assert fields.merchant is None
    assert fields.date is None
    assert fields.total is None


FORM = """
DEPARTMENT OF HEALTH
APPLICATION FOR LICENSE
Form No. 4412-A
DATE: 14/03/1986
NAME OF APPLICANT
"""


def test_form_parser_title_date_reference():
    fields = parse_form_text(FORM)
    assert fields.title and "DEPARTMENT OF HEALTH" in fields.title.upper()
    assert fields.date == "14/03/1986"
    assert fields.reference == "4412-A"
    assert fields.merchant is None
    assert fields.total is None


def test_parse_document_dispatches():
    receipt = parse_document(STARBUCKS, "receipt")
    form = parse_document(FORM, "form")
    assert receipt.merchant and "STARBUCKS" in receipt.merchant.upper()
    assert form.title and "DEPARTMENT" in form.title.upper()
