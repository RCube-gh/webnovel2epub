from narou2kindle.narou import format_blocks


def test_reflows_prose_to_paragraph_length():
    blocks = format_blocks(["地の文その一。", "地の文その二。", "地の文その三。"], paragraph_length=14)
    assert [block.text for block in blocks] == ["地の文その一。地の文その二。", "地の文その三。"]
    assert all(block.kind == "prose" for block in blocks)


def test_dialogue_and_scene_break_are_own_blocks():
    blocks = format_blocks(["地の文。", "「会話文。」", "地の文。", "◇◇◇", "　次の場面。"], section_length=0)
    assert [(block.text, block.kind) for block in blocks] == [
        ("地の文。", "prose"),
        ("「会話文。」", "dialogue"),
        ("地の文。", "prose"),
        ("", "blank"),
        ("◇◇◇", "scene-break"),
        ("", "blank"),
        ("次の場面。", "prose"),
    ]


def test_white_diamond_scene_break_has_blank_blocks_on_both_sides():
    blocks = format_blocks(["前の地の文。", "♢♢♢", "後ろの地の文。"], section_length=0)
    assert [(block.text, block.kind) for block in blocks] == [
        ("前の地の文。", "prose"),
        ("", "blank"),
        ("♢♢♢", "scene-break"),
        ("", "blank"),
        ("後ろの地の文。", "prose"),
    ]


def test_full_width_indents_do_not_force_a_paragraph_break():
    blocks = format_blocks(["　地の文その一。", "　地の文その二。"], paragraph_length=100, section_length=0)
    assert [(block.text, block.kind) for block in blocks] == [("地の文その一。地の文その二。", "prose")]


def test_section_break_waits_until_a_dialogue_run_ends():
    blocks = format_blocks(["地の文。", "「会話その一。」", "「会話その二。」", "続く地の文。"], section_length=1)
    assert [(block.text, block.kind) for block in blocks] == [
        ("地の文。", "prose"),
        ("", "blank"),
        ("「会話その一。」", "dialogue"),
        ("「会話その二。」", "dialogue"),
        ("", "blank"),
        ("続く地の文。", "prose"),
    ]
