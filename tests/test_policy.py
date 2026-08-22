from storycanvas.policy import check_public_image_policy, is_visually_relevant


def test_public_policy_blocks_explicit_content() -> None:
    assert not check_public_image_policy("explicit sex scene").allowed
    assert not check_public_image_policy("血腥肢解").allowed


def test_public_policy_allows_adventure_scene() -> None:
    assert check_public_image_policy("旅人进入雨夜中的城堡大厅").allowed
    assert is_visually_relevant("旅人看见森林里的古老城堡")
