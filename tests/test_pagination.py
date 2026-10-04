from app.pagination import parse_page_args, paginate, page_url, ALLOWED_PER_PAGE


class _Q:
    def __init__(self, n):
        self.n = n

    def count(self):
        return self.n

    def offset(self, off):
        self._off = off
        return self

    def limit(self, lim):
        self._lim = lim
        return self

    def all(self):
        return list(range(self._off, min(self._off + self._lim, self.n)))


def test_parse_page_args():
    assert parse_page_args(0, 25) == (1, 25)
    assert parse_page_args(2, 99) == (2, 25)  # invalid per_page → default
    assert parse_page_args(3, 50) == (3, 50)


def test_paginate():
    pg = paginate(_Q(100), page=2, per_page=10)
    assert pg["page"] == 2
    assert pg["pages"] == 10
    assert pg["total"] == 100
    assert pg["rows"] == list(range(10, 20))
    assert pg["count"] == 10
    assert pg["has_prev"] and pg["has_next"]


def test_page_url():
    u = page_url("/phones/", 2, 25, q="t46")
    assert "page=2" in u
    assert "per_page=25" in u
    assert "q=t46" in u
