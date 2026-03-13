"""Resume-specific content selection logic.

Contains the experience block scoring and deterministic suppression rules
that are specific to the resume document type.
"""

import logging
import re
from collections import defaultdict

from doc_tailor.models import (
    MatchStrength,
    PriorityTier,
    RequirementMapping,
    SuppressionEntry,
)
from doc_tailor.plugins.resume.models import ExperienceBlock, ParsedResume

logger = logging.getLogger(__name__)

# Pattern for detecting metrics/numbers in bullets
_METRIC_PATTERN = re.compile(r'\d+[%xX]|\$[\d,]+|\d{2,}|#\d+')


def _score_experience_block(
    block: ExperienceBlock,
    evidence_map: list[RequirementMapping],
) -> float:
    """Score an experience block by how well its bullets match requirements.

    Scoring:
    - Each strong match to a must_have requirement: 10 points
    - Each strong match to a strong_preference: 6 points
    - Each strong match to a nice_to_have: 3 points
    - Weak matches get half the points
    - Bonus for number of distinct requirements covered
    """
    bullet_texts = {b.text for b in block.bullets}
    score = 0.0
    requirements_covered = set()

    priority_weights = {
        PriorityTier.MUST_HAVE: 10.0,
        PriorityTier.STRONG_PREFERENCE: 6.0,
        PriorityTier.NICE_TO_HAVE: 3.0,
    }
    strength_multiplier = {
        MatchStrength.STRONG: 1.0,
        MatchStrength.WEAK: 0.5,
        MatchStrength.NONE: 0.0,
    }

    for mapping in evidence_map:
        for entry in mapping.evidence:
            if entry.source_text in bullet_texts:
                weight = priority_weights.get(mapping.priority, 3.0)
                mult = strength_multiplier.get(entry.match_strength, 0.0)
                score += weight * mult
                if mult > 0:
                    requirements_covered.add(mapping.requirement)

    score += len(requirements_covered) * 2.0

    return score


def compute_resume_suppressions(
    evidence_map: list[RequirementMapping],
    parsed_source,
    config,
) -> list[SuppressionEntry]:
    """Apply resume-specific suppression logic.

    Operates at two levels:
    1. Experience-block level: rank blocks by relevance, suppress the weakest
    2. Bullet level: within kept blocks, suppress beyond per-block targets
    """
    parsed_resume: ParsedResume = parsed_source
    plugin_config = config.plugin_config
    max_experiences = plugin_config.get("max_experiences", 4)
    min_bullets = plugin_config.get("min_bullets_per_block", 2)
    base_target = plugin_config.get("base_bullet_target", 2.5)
    max_target = plugin_config.get("max_bullet_target", 5)

    suppressions = []
    all_bullets = parsed_resume.all_bullets()

    # --- Phase 1: Experience block ranking and suppression ---
    blocks = parsed_resume.experience_blocks
    suppressed_block_ids: set[str] = set()

    if max_experiences > 0 and len(blocks) > max_experiences:
        block_scores = []
        for block in blocks:
            score = _score_experience_block(block, evidence_map)
            block_scores.append((block, score))
            logger.debug(
                f"Block '{block.experience_id}' "
                f"({block.company or block.title}): score={score:.1f}"
            )

        block_scores.sort(key=lambda x: x[1], reverse=True)

        kept = block_scores[:max_experiences]
        cut = block_scores[max_experiences:]

        logger.info(
            f"Experience selection: keeping {len(kept)}/{len(blocks)} blocks "
            f"(top scores: {[f'{s:.0f}' for _, s in kept]})"
        )

        for block, score in cut:
            suppressed_block_ids.add(block.experience_id)
            for bullet in block.bullets:
                suppressions.append(SuppressionEntry(
                    source_text=bullet.text,
                    section_id=bullet.experience_id,
                    reason=f"experience block suppressed (relevance score: {score:.0f}, "
                           f"below top {max_experiences})",
                ))

    # --- Phase 2: Compute per-block bullet targets ---
    kept_blocks = [b for b in blocks if b.experience_id not in suppressed_block_ids]
    if not kept_blocks:
        kept_blocks = blocks

    block_score_map = {b.experience_id: _score_experience_block(b, evidence_map)
                       for b in kept_blocks}
    max_score = max(block_score_map.values()) if block_score_map else 1.0
    max_score = max(max_score, 1.0)

    extra_range = max_target - base_target
    bullet_targets: dict[str, int] = {}
    for exp_id, score in block_score_map.items():
        normalized = score / max_score
        raw_target = base_target + extra_range * normalized
        target = max(min_bullets, min(max_target, round(raw_target)))
        bullet_targets[exp_id] = target

    logger.info(
        f"Bullet targets: "
        + ", ".join(f"{eid}={t}" for eid, t in bullet_targets.items())
    )

    # --- Phase 3: Bullet-level suppression within kept blocks ---
    mapped_texts: set[str] = set()
    text_to_requirements: dict[str, list[tuple[str, MatchStrength]]] = {}

    for mapping in evidence_map:
        for entry in mapping.evidence:
            mapped_texts.add(entry.source_text)
            if entry.source_text not in text_to_requirements:
                text_to_requirements[entry.source_text] = []
            text_to_requirements[entry.source_text].append(
                (mapping.requirement, entry.match_strength)
            )

    already_suppressed = {s.source_text for s in suppressions}

    block_bullets: dict[str, list] = defaultdict(list)
    for bullet in all_bullets:
        if bullet.experience_id not in suppressed_block_ids:
            block_bullets[bullet.experience_id].append(bullet)

    for exp_id, exp_bullets in block_bullets.items():
        target = bullet_targets.get(exp_id, min_bullets)

        def _bullet_retention_score(b):
            reqs = text_to_requirements.get(b.text, [])
            if reqs:
                best = min(
                    (0 if s == MatchStrength.STRONG else 1)
                    for _, s in reqs
                )
                return best
            has_metric = bool(_METRIC_PATTERN.search(b.text))
            return 2 if has_metric else 3

        ranked = sorted(exp_bullets, key=_bullet_retention_score)

        kept_count = 0
        for bullet in ranked:
            if bullet.text in already_suppressed:
                continue
            kept_count += 1
            if kept_count > target:
                suppressions.append(SuppressionEntry(
                    source_text=bullet.text,
                    section_id=bullet.experience_id,
                    reason="below bullet target (low relevance)",
                ))
                already_suppressed.add(bullet.text)

    # Rule: Duplicate evidence
    req_to_bullets: dict[str, list[tuple[str, str, MatchStrength]]] = {}
    for mapping in evidence_map:
        for entry in mapping.evidence:
            if entry.section_id in suppressed_block_ids:
                continue
            key = mapping.requirement
            if key not in req_to_bullets:
                req_to_bullets[key] = []
            req_to_bullets[key].append(
                (entry.source_text, entry.section_id, entry.match_strength)
            )

    for req, bullets in req_to_bullets.items():
        if len(bullets) <= 1:
            continue
        strength_order = {
            MatchStrength.STRONG: 0,
            MatchStrength.WEAK: 1,
            MatchStrength.NONE: 2,
        }
        sorted_bullets = sorted(
            bullets, key=lambda x: strength_order.get(x[2], 2)
        )
        for bullet_text, exp_id, strength in sorted_bullets[1:]:
            if bullet_text not in already_suppressed:
                block_remaining = sum(
                    1 for b in block_bullets.get(exp_id, [])
                    if b.text not in already_suppressed
                )
                if block_remaining <= min_bullets:
                    continue
                other_reqs = [
                    r for r, s in text_to_requirements.get(bullet_text, [])
                    if r != req
                ]
                if not other_reqs:
                    suppressions.append(SuppressionEntry(
                        source_text=bullet_text,
                        section_id=exp_id,
                        reason=f"duplicate evidence for: {req}",
                    ))
                    already_suppressed.add(bullet_text)

    return suppressions
