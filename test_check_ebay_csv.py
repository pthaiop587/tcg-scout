"""Tests for the pre-flight check.

Run: python -m pytest test_check_ebay_csv.py

The point of the check is to fail here rather than in a results file hours
later, so what matters is that it catches the things eBay actually refuses and
does not cry wolf on a file that is fine. A check that flags everything gets
ignored, which is the same as not having one.
"""

import check_ebay_csv as k

ACTION = "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)"
FIELDS = [ACTION, "CustomLabel", "Category", "Title", "ConditionID",
          "PicURL", "StartPrice", "Quantity", "ShippingProfileName",
          "ShippingService-1:Cost"]


def row(**kw):
    d = {ACTION: "Add", "CustomLabel": "CRH-0001", "Category": "261328",
         "Title": "2025 Panini Prizm Arch Manning #166 RC", "ConditionID":
         "4000", "PicURL": "https://i.ebayimg.com/a.jpg", "StartPrice": "13",
         "Quantity": "1", "ShippingProfileName": "",
         "ShippingService-1:Cost": "1.50"}
    d.update(kw)
    return d


def stops(rows, fields=None):
    return [m for sev, _sku, m in k.check(rows, fields or FIELDS)
            if sev == "STOP"]


def warns(rows, fields=None):
    return [m for sev, _sku, m in k.check(rows, fields or FIELDS)
            if sev == "WARN"]


# --- a good file is left alone ----------------------------------------------

def test_a_sound_row_raises_nothing():
    assert k.check([row()], FIELDS) == []


# --- what eBay refuses ------------------------------------------------------

def test_a_duplicate_sku_is_caught():
    """eBay keys revisions off CustomLabel, so two rows sharing one is a
    listing that overwrites its neighbour."""
    got = stops([row(), row()])
    assert any("same CustomLabel" in m for m in got)


def test_a_title_over_eighty_is_caught():
    got = stops([row(Title="x" * 81)])
    assert any("1 over the limit" in m for m in got)


def test_an_empty_title_is_caught():
    assert any("no title" in m for m in stops([row(Title="")]))


def test_a_missing_or_zero_price_is_caught():
    assert any("no start price" in m for m in stops([row(StartPrice="")]))
    assert any("0.00" in m for m in stops([row(StartPrice="0")]))


def test_a_price_with_a_dollar_sign_is_still_a_price():
    """Not every spelling of a number is a mistake."""
    assert stops([row(StartPrice="$13.00")]) == []


def test_a_picture_that_is_not_https_is_caught():
    """eBay fails the call outright for a non-HTTPS picture host."""
    got = stops([row(PicURL="http://example.com/a.jpg")])
    assert any("not https" in m for m in got)


def test_too_many_pictures_is_caught():
    got = stops([row(PicURL="|".join(["https://i.ebayimg.com/%d.jpg" % i
                                      for i in range(30)]))])
    assert any("eBay takes 24" in m for m in got)


def test_a_missing_action_column_is_caught():
    got = stops([row()], [f for f in FIELDS if f != ACTION])
    assert any("no Action column" in m for m in got)


def test_a_missing_category_is_caught():
    assert any("no category" in m for m in stops([row(Category="")]))


# --- what is only worth a look ----------------------------------------------

def test_a_row_with_no_picture_warns_but_does_not_stop():
    assert any("no picture" in m for m in warns([row(PicURL="")]))
    assert stops([row(PicURL="")]) == []


def test_postage_declared_twice_is_flagged():
    got = warns([row(ShippingProfileName="Cards $1.50",
                     **{"ShippingService-1:Cost": "1.50"})])
    assert any("one or the other" in m for m in got)


def test_no_postage_at_all_is_flagged():
    got = warns([row(ShippingProfileName="",
                     **{"ShippingService-1:Cost": ""})])
    assert any("no postage at all" in m for m in got)


def test_a_shipping_profile_alone_is_fine():
    """Most accounts are on Business Policies; that is not a problem."""
    got = warns([row(ShippingProfileName="Cards $1.50",
                     **{"ShippingService-1:Cost": ""})])
    assert not any("postage" in m for m in got)
