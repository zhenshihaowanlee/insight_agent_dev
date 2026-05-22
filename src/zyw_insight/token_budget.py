from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "configs" / "fulltext_token_policy.json"
SECTION_MARKERS = {
    "abstract": ("abstract",),
    "introduction": ("introduction",),
    "background": ("background", "motivation"),
    "method_or_design": ("method", "design", "architecture", "implementation", "system"),
    "evaluation_or_experiments": ("evaluation", "experiment", "results", "measurement"),
    "limitations_or_discussion": ("limitation", "discussion", "future work"),
    "references": ("references",),
}
MODEL_FACTORS = {
    "openrouter/qwen/qwen3.5-397b-a17b": 2.2,
    "qwen/qwen3.5-397b-a17b": 2.2,
}
DEFAULT_CONSERVATIVE_FACTOR = 2.2


def load_fulltext_token_policy(path: str | Path | None = None) -> Dict[str, Any]:
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    return json.loads(policy_path.read_text(encoding="utf-8"))["one_shot_full_paper"]


def estimate_tokens_rough(text: str) -> int:
    return int(math.ceil(len(text or "") / 3.5))


def calibrate_token_estimate(rough_estimate: int, model_id: str) -> int:
    factor = MODEL_FACTORS.get(str(model_id), DEFAULT_CONSERVATIVE_FACTOR)
    factor = max(float(factor), DEFAULT_CONSERVATIVE_FACTOR)
    return int(math.ceil(int(rough_estimate) * factor))


def estimate_tokens_conservative(text: str, provider: str = "qwen") -> int:
    model_id = provider if str(provider).startswith("openrouter/") else str(provider)
    return calibrate_token_estimate(estimate_tokens_rough(text), model_id)


def _sha_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _coverage(text: str) -> Dict[str, bool]:
    lowered = (text or "").lower()
    return {name: any(marker in lowered for marker in markers) for name, markers in SECTION_MARKERS.items()}


def select_fulltext_for_one_shot_analysis(text: str, target_input_tokens: int, max_input_tokens_hard: int) -> Dict[str, Any]:
    original = text or ""
    if estimate_tokens_rough(original) <= max_input_tokens_hard:
        selected = original
        strategy = "full_extracted_text_fits"
    else:
        max_chars = int(max_input_tokens_hard * 3.5)
        head_chars = int(max_chars * 0.65)
        tail_chars = max(0, max_chars - head_chars - 120)
        selected = original[:head_chars] + "\n\n[...middle omitted for one-shot token budget...]\n\n" + original[-tail_chars:]
        strategy = "section_aware_head_tail_truncation"
    return {
        "selected_text": selected,
        "selected_text_sha256": _sha_text(selected),
        "included_char_count": len(selected),
        "estimated_input_tokens": estimate_tokens_rough(selected),
        "selection_strategy": strategy,
        "omitted_char_count": max(0, len(original) - len(selected)),
        "section_coverage": _coverage(selected),
        "target_input_tokens": int(target_input_tokens),
        "max_input_tokens_hard": int(max_input_tokens_hard),
    }


def _score_paragraph(paragraph: str) -> int:
    lowered = paragraph.lower()
    preferred = (
        "architecture",
        "implementation",
        "method",
        "design",
        "evaluation",
        "experiment",
        "baseline",
        "result",
        "limitation",
        "conclusion",
        "latency",
        "throughput",
        "gpu",
        "moe",
        "inference",
        "communication",
        "m2n",
    )
    return sum(3 for marker in preferred if marker in lowered) + min(len(paragraph) // 500, 3)


def select_fulltext_under_token_cap(text: str, target_input_tokens: int, max_input_tokens_hard: int, model_id: str) -> Dict[str, Any]:
    original = text or ""
    prompt_overhead_tokens = 1800
    usable_cap = max(1000, min(int(target_input_tokens), int(max_input_tokens_hard) - prompt_overhead_tokens))
    full_rough = estimate_tokens_rough(original)
    full_conservative = calibrate_token_estimate(full_rough, model_id)
    if full_conservative + prompt_overhead_tokens <= int(max_input_tokens_hard):
        selected = original
        strategy = "full_extracted_text_fits_conservative_cap"
        selected_sections = [name for name, present in _coverage(selected).items() if present]
    else:
        paragraphs = [p.strip() for p in original.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in original.splitlines() if p.strip()]
        chosen: list[str] = []
        running = 0
        intro = paragraphs[:6]
        tail = paragraphs[-4:] if len(paragraphs) > 10 else []
        prioritized = sorted(paragraphs[6:-4] if len(paragraphs) > 10 else paragraphs[6:], key=_score_paragraph, reverse=True)
        for para in intro + prioritized + tail:
            addition = para if not chosen else "\n\n" + para
            projected = calibrate_token_estimate(estimate_tokens_rough("".join(chosen) + addition), model_id)
            if projected <= usable_cap:
                chosen.append(addition)
            if projected >= usable_cap:
                break
        selected = "".join(chosen)
        if not selected:
            max_chars = max(1, int((usable_cap / DEFAULT_CONSERVATIVE_FACTOR) * 3.5))
            head_chars = int(max_chars * 0.7)
            tail_chars = max(0, max_chars - head_chars - 120)
            selected = original[:head_chars] + "\n\n[...middle omitted for conservative one-shot token cap...]\n\n" + original[-tail_chars:]
        strategy = "section_aware_conservative_token_cap"
        selected_sections = [name for name, present in _coverage(selected).items() if present]
    rough = estimate_tokens_rough(selected)
    conservative = calibrate_token_estimate(rough, model_id)
    all_sections = set(SECTION_MARKERS)
    return {
        "selected_text": selected,
        "selected_text_sha256": _sha_text(selected),
        "included_char_count": len(selected),
        "estimated_input_tokens": conservative,
        "rough_estimated_input_tokens": rough,
        "conservative_estimated_input_tokens": conservative,
        "max_input_tokens_hard": int(max_input_tokens_hard),
        "target_input_tokens": int(target_input_tokens),
        "omitted_char_count": max(0, len(original) - len(selected)),
        "selected_sections": selected_sections,
        "omitted_sections": sorted(all_sections - set(selected_sections)),
        "truncation_strategy": strategy,
        "selection_strategy": strategy,
        "section_coverage": _coverage(selected),
        "expected_actual_input_safe": conservative + prompt_overhead_tokens <= int(max_input_tokens_hard),
    }


def validate_one_shot_token_budget(
    estimated_input_tokens: int,
    max_output_tokens: int,
    max_total_tokens_hard: int,
    model_context_length: int | None = None,
) -> Dict[str, Any]:
    total = int(estimated_input_tokens) + int(max_output_tokens)
    context_limit = model_context_length or int(max_total_tokens_hard)
    ok = total <= int(max_total_tokens_hard) and total <= context_limit
    errors = []
    if total > int(max_total_tokens_hard):
        errors.append("estimated input plus max output exceeds max_total_tokens_hard")
    if model_context_length is not None and total > int(model_context_length):
        errors.append("estimated input plus max output exceeds known model context length")
    return {
        "ok": ok,
        "estimated_total_tokens": total,
        "model_context_length": model_context_length,
        "max_total_tokens_hard": int(max_total_tokens_hard),
        "errors": errors,
    }


def build_prompt_inclusion_audit(
    extracted_text_sha256: str,
    extracted_char_count: int,
    selection: Dict[str, Any],
    min_input_tokens_required: int,
    target_input_tokens: int,
    max_input_tokens_hard: int,
    max_output_tokens_hard: int,
    max_total_tokens_hard: int,
) -> Dict[str, Any]:
    estimated = int(selection.get("conservative_estimated_input_tokens") or selection["estimated_input_tokens"])
    return {
        "extracted_text_sha256": extracted_text_sha256,
        "extracted_char_count": int(extracted_char_count),
        "selected_text_sha256": selection["selected_text_sha256"],
        "included_char_count": int(selection["included_char_count"]),
        "estimated_input_tokens": estimated,
        "rough_estimated_input_tokens": int(selection.get("rough_estimated_input_tokens") or estimated),
        "conservative_estimated_input_tokens": estimated,
        "min_input_tokens_required": int(min_input_tokens_required),
        "target_input_tokens": int(target_input_tokens),
        "max_input_tokens_hard": int(max_input_tokens_hard),
        "max_output_tokens_hard": int(max_output_tokens_hard),
        "max_total_tokens_hard": int(max_total_tokens_hard),
        "prompt_includes_fulltext_excerpt": True,
        "one_shot_fulltext_attempt": True,
        "full_text_not_really_sent_planned": estimated < int(min_input_tokens_required),
        "selection_strategy": selection["selection_strategy"],
        "truncation_strategy": selection.get("truncation_strategy", selection["selection_strategy"]),
        "omitted_char_count": int(selection["omitted_char_count"]),
        "selected_sections": selection.get("selected_sections", []),
        "omitted_sections": selection.get("omitted_sections", []),
        "expected_actual_input_safe": bool(selection.get("expected_actual_input_safe", estimated <= int(max_input_tokens_hard))),
        "section_coverage": selection["section_coverage"],
    }
