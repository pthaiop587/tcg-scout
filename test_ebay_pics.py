"""Tests for the eBay Picture Services uploader.

Run: python -m pytest test_ebay_pics.py

Nothing here calls eBay. What can be tested without an account is the part
that is easy to get wrong and hard to debug through an API: the shape of the
multipart body, whether a failure is recognised as one, and whether a token
can leak into somewhere it should not be.

That last one matters most. eBay answers HTTP 200 for failures, with the
reason in the body, so "it did not raise" is not "it worked" -- and a run that
silently records no URLs looks identical to a run with nothing to do.
"""

import json

import pytest

import ebay_pics as ep

CREDS = {"dev_id": "D", "app_id": "A", "cert_id": "C", "token": "TOK"}


# --- the request ------------------------------------------------------------

def test_the_xml_comes_before_the_image():
    """eBay rejects the call if the parts are the other way round, with an
    error that does not mention the order."""
    body = ep.multipart(ep.payload("CRH-0001 front", "TOK"), b"\xff\xd8JPEG",
                        "CRH-0001.jpg")
    assert body.index(b"XML Payload") < body.index(b"filename=")
    assert body.index(b"filename=") < body.index(b"\xff\xd8JPEG")


def test_the_body_is_a_well_formed_multipart():
    body = ep.multipart(ep.payload("x", "TOK"), b"IMG", "a.jpg")
    assert body.startswith(("--" + ep.BOUNDARY).encode())
    assert body.rstrip().endswith(("--%s--" % ep.BOUNDARY).encode())
    assert body.count(("--" + ep.BOUNDARY).encode()) == 3  # two parts + close


def test_the_image_bytes_are_not_mangled():
    """A jpeg is not text. Any encode/decode on the way through corrupts it."""
    blob = bytes(range(256))
    assert blob in ep.multipart(ep.payload("x", "T"), blob, "a.jpg")


def test_a_name_with_an_ampersand_does_not_break_the_xml():
    x = ep.payload("Topps S&S <Chrome>", "TOK")
    assert "&amp;" in x and "&lt;Chrome&gt;" in x
    assert "S&S" not in x


# --- reading the answer -----------------------------------------------------

def test_a_good_answer_yields_the_url():
    url, err = ep.full_url(
        "<Ack>Success</Ack><SiteHostedPictureDetails>"
        "<FullURL>https://i.ebayimg.com/00/s/abc.jpg</FullURL>"
        "</SiteHostedPictureDetails>")
    assert err is None
    assert url == "https://i.ebayimg.com/00/s/abc.jpg"


def test_a_failure_is_reported_even_though_ebay_said_200():
    url, err = ep.full_url(
        "<Ack>Failure</Ack><Errors><ShortMessage>Invalid token</ShortMessage>"
        "<LongMessage>Auth token is invalid or expired.</LongMessage>"
        "</Errors>")
    assert url is None
    assert "Failure" in err
    assert "expired" in err


def test_an_empty_answer_is_a_failure_not_a_url():
    url, err = ep.full_url("")
    assert url is None and err


# --- credentials ------------------------------------------------------------

def test_missing_credentials_stop_before_anything_is_uploaded(tmp_path,
                                                              monkeypatch):
    for f in ep.FIELDS:
        monkeypatch.delenv("EBAY_" + f.upper(), raising=False)
    with pytest.raises(SystemExit) as e:
        ep.load_creds(str(tmp_path / "nope.json"))
    assert "developer.ebay.com" in str(e.value), "say where to get them"


def test_credentials_can_come_from_the_environment(tmp_path, monkeypatch):
    """So the token need never sit on disk."""
    for f in ep.FIELDS:
        monkeypatch.setenv("EBAY_" + f.upper(), "env-" + f)
    got = ep.load_creds(str(tmp_path / "nope.json"))
    assert got["token"] == "env-token"


def test_the_file_wins_over_the_environment(tmp_path, monkeypatch):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(CREDS), encoding="utf-8")
    for f in ep.FIELDS:
        monkeypatch.setenv("EBAY_" + f.upper(), "env-" + f)
    assert ep.load_creds(str(p))["token"] == "TOK"


def test_the_credentials_file_is_gitignored():
    """A user token is a password, and this one lives in the project folder."""
    with open(".gitignore", encoding="utf-8") as fh:
        assert "ebay-credentials.json" in fh.read()


# --- what the exporter does with the result ---------------------------------

def test_the_exporter_prefers_an_ebay_hosted_picture(tmp_path, monkeypatch):
    """Once eBay hosts it, no public site needs to exist at all."""
    import make_ebay_csv as m
    p = tmp_path / "eps.json"
    p.write_text(json.dumps({"CRH-0122": ["https://i.ebayimg.com/a.jpg",
                                          "https://i.ebayimg.com/b.jpg"]}),
                 encoding="utf-8")
    monkeypatch.setattr(m, "EPS_URLS", str(p))
    got = m.photo_urls("CRH-0122")
    assert got == "https://i.ebayimg.com/a.jpg|https://i.ebayimg.com/b.jpg"
    assert "github" not in got


def test_a_card_eBay_does_not_host_yet_still_falls_back_to_pages(tmp_path,
                                                                 monkeypatch):
    """The two hosts coexist while the collection moves across."""
    import make_ebay_csv as m
    p = tmp_path / "eps.json"
    p.write_text(json.dumps({"CRH-0122": ["https://i.ebayimg.com/a.jpg"]}),
                 encoding="utf-8")
    monkeypatch.setattr(m, "EPS_URLS", str(p))
    assert m.photo_urls("CRH-0122").startswith("https://i.ebayimg.com/")
    assert "i.ebayimg.com" not in m.photo_urls("CRH-0001")
