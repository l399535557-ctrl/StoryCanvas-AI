from storycanvas.commands import ImageCommand, parse_command


def test_chinese_commands() -> None:
    assert parse_command("/图 城堡大厅").command is ImageCommand.FORCE
    assert parse_command("/图 城堡大厅").text == "城堡大厅"
    assert parse_command("/图开").command is ImageCommand.ENABLE
    assert parse_command("/图关").command is ImageCommand.DISABLE


def test_english_commands() -> None:
    assert parse_command("/image: rainy city").text == "rainy city"
    assert parse_command("/image-on").command is ImageCommand.ENABLE
    assert parse_command("ordinary action").command is ImageCommand.NONE
