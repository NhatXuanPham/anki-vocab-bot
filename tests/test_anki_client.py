from anki_client import get_existing_vocab_data, word_exists_in_deck


def test_word_exists_in_deck_matches_word_field_exactly(monkeypatch):
    calls = []

    def fake_invoke(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [1, 2] if "findNotes" in action else []
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


def test_get_existing_vocab_data_parses_html_word_and_base(monkeypatch):
    def fake_invoke(action, **params):
        if action == "findNotes":
            return [10]
        if action == "notesInfo":
            return [
                {
                    "fields": {
                        "Word": {
                            "value": '<div style="font-size:30px;">went</div><div style="color:#777;">Base word: go</div>'
                        },
                        "Phonetic": {"value": "/weŋt/"},
                        "PartOfSpeech": {"value": "v."},
                        "MeaningVi": {"value": "đã đi"},
                        "MeaningEn": {"value": "past of go"},
                        "ExampleEn": {"value": "I went home."},
                        "ExampleVi": {"value": "Tôi đã về nhà."},
                        "Audio": {"value": "[sound:went.mp3]"},
                    }
                }
            ]
        raise AssertionError(f"unexpected action: {action}")

    monkeypatch.setattr("anki_client._invoke", fake_invoke)

    data = get_existing_vocab_data("went", base_word="go")
    assert data is not None
    assert data["word"] == "went"
    assert data["base_word"] == "go"
    assert data["phonetic"] == "/weŋt/"
    assert data["meaning_vi"] == "đã đi"
    assert data["audio"] == "[sound:went.mp3]"

