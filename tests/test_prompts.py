from storycanvas.prompts import compile_visual_prompt, parse_json_object_text


def test_json_extractor_accepts_fenced_output_and_trailing_prose() -> None:
    parsed = parse_json_object_text(
        'Result:\n```json\n{"subjects":["one explorer"]}\n```\nDone.'
    )
    assert parsed == {"subjects": ["one explorer"]}


def test_visual_prompt_has_stable_sections_and_deduplicates_tags() -> None:
    positive, negative = compile_visual_prompt(
        {
            "subjects": ["one explorer", "one explorer"],
            "face_body_identity": "amber eyes, short black hair",
            "camera_composition": ["medium shot", "low angle"],
            "lighting_color": ["warm key light", "cool rim light"],
            "negative": ["blurry", "blurry", "text"],
        }
    )
    assert positive.count("one explorer") == 1
    assert " BREAK " in positive
    assert "medium shot" in positive
    assert negative == "blurry, text"
