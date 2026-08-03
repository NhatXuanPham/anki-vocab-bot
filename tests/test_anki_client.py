from anki_client import word_exists_in_deck


def test_word_exists_in_deck_matches_word_field_exactly(monkeypatch):
    calls = []

    def fake_invoke(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [1, 2] if params.get("query", "").startswith('deck:"') else []
        if action == "notesInfo":
            return [
                {"fields": {"Word": {"value": "statement"}}},
                {"fields": {"Word": {"value": "another"}}},
            ]
        raise AssertionError(f"unexpected action: {action}")

    monkeypatch.setattr("anki_client._invoke", fake_invoke)

    assert word_exists_in_deck("statement") is True
    assert word_exists_in_deck("stat") is False
    assert calls[0][0] == "findNotes"
    assert calls[1][0] == "notesInfo"
