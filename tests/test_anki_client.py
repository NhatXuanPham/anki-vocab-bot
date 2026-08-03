from anki_client import word_exists_in_deck


def test_word_exists_in_deck_uses_normalized_query(monkeypatch):
    calls = []

    def fake_invoke(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [1, 2]
        raise AssertionError(f"unexpected action: {action}")

    monkeypatch.setattr("anki_client._invoke", fake_invoke)

    assert word_exists_in_deck("Hello") is True
    assert calls[0][0] == "findNotes"
    assert "deck" in calls[0][1]["query"].lower()
    assert "hello" in calls[0][1]["query"].lower()
