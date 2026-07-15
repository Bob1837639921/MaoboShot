from dataclasses import dataclass


@dataclass(frozen=True)
class PetTranslationState:
    state: str
    result_text: str
    engine_label: str
    has_failure: bool


def resolve_translation_state(results: dict) -> PetTranslationState:
    ai_text = (results.get("doubao", "") or "").strip()
    google_text = (results.get("google", "") or "").strip()
    ai_error = (results.get("doubao_error", "") or "").strip()
    ai_loading = bool(results.get("doubao_loading", False))
    google_loading = bool(results.get("google_loading", False))
    ai_enabled = bool(results.get("ai_enabled", True))

    ai_ok = bool(ai_text)
    google_ok = bool(google_text) and not google_text.startswith("❌")
    result_text = ai_text or (google_text if google_ok else "")

    if ai_loading or google_loading:
        return PetTranslationState(
            state="translating",
            result_text=result_text,
            engine_label="AI 流式输出" if ai_text else ("Google" if google_ok else "处理中"),
            has_failure=False,
        )

    if ai_ok or google_ok:
        has_failure = bool(ai_error) or (ai_enabled and not ai_ok) or not google_ok
        return PetTranslationState(
            state="partial_error" if has_failure else "success",
            result_text=result_text,
            engine_label="部分完成" if has_failure else ("AI" if ai_ok else "Google"),
            has_failure=has_failure,
        )

    return PetTranslationState(
        state="error",
        result_text="",
        engine_label="需要重试",
        has_failure=True,
    )
