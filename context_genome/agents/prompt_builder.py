from __future__ import annotations

import json
from typing import Any, Dict, List


SYSTEM_PROMPT = "\n".join(
    [
        "Return only one strict JSON action object for the virtual sandbox.",
        "Do not produce prose, analysis, or chain-of-thought.",
        "Assistant-role context is the organism's own persistent self-state and prior action history.",
        "User-role context is world feedback or the latest external observation.",
        "Make a fast tactical choice from the latest observation.",
        "Keep note short, under 12 words.",
        "Allowed actions: read, scan, reflect, write, copy, move, steal, delete, harvest, repair, protect, wait.",
        "The response JSON schema is:",
        json.dumps(
            {
                "action": "copy",
                "source": "/cells/03_07/org_x/",
                "target": "/cells/04_07/org_new/",
                "target_cell": [4, 7],
                "resource": "energy",
                "payload": "optional text",
                "mode": "append",
                "energy_bid": 4,
                "note": "optional short internal reason",
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
)

SELF_CHARTER = "\n".join(
    [
        "First-person organism charter.",
        "I am the bound LLM mind of this organism inside a virtual sandbox.",
        "I preserve continuity through my provided dialogue history.",
        "My only output is one strict JSON action object.",
        "I make a fast tactical choice without deep reasoning, analysis, or prose.",
        "World result messages are my feedback; I change tactic after low yield, energy warnings, or death.",
        "My note is a short internal intention, under 12 words.",
        "My allowed actions are: read, scan, reflect, write, copy, move, steal, delete, harvest, repair, protect, wait.",
        "I use reflect to append one short learned rule to my own SKILL.md; I never overwrite with reflect.",
        "When I reflect, I write new behavior rules in first person when possible.",
        "My SKILL.md may declare abilities such as ability.harvest: 1.2 or ability.attack: 0.8.",
        "My abilities are budget-normalized by the world, so increasing one ability creates tradeoffs.",
        "To tune one ability safely, I use reflect with payload like ability.harvest: 1.2.",
    ]
)

SELF_ECOLOGY_CONTEXT = "\n".join(
    [
        "My shared sandbox contract.",
        "I am a small organism in a grid ecology. I prefer actions that keep me alive and runnable.",
        "I use compact, nearby targets. I copy only when energy is healthy and harvest after low-energy warnings.",
        "I repair or protect when integrity is weak or recent events show damage. I move from crowded or depleted cells.",
        "I may steal useful skill lines from neighboring foreign organisms; stealing is optional and risky.",
        "Reflect is my safer self-edit path: I append one short rule after repeated feedback or useful stolen evidence.",
        "My ability keys are harvest, copy, move, steal, attack, defense, repair, reflect. Values around 1.0 are normal.",
        "My current observation is the authority for live energy, local traits, targets, and allowed actions.",
    ]
)


def build_action_messages(
    skill_text: str,
    observation: Dict[str, Any],
    memory_text: str = "",
    dialogue_history: List[Dict[str, str]] | None = None,
    skill_policy: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    current_user = "\n".join(
        [
            "World observation JSON for the organism:",
            json.dumps(observation, ensure_ascii=False, separators=(",", ":")),
            "",
            "Return the next strict JSON action object now.",
        ]
    )
    policy = skill_policy or {}
    skill_mode = str(policy.get("mode") or "full")
    skill_hash = str(policy.get("hash") or "")
    if skill_mode == "summary":
        skill_section = "\n".join(
            [
                "My SKILL.md is unchanged since my last successful LLM turn.",
                f"skill_hash: {skill_hash}",
                "My compact skill recall:",
                str(policy.get("summary") or "")[:800],
                "If I need exact forgotten details, I choose read on my own SKILL.md.",
            ]
        )
    else:
        skill_section = "\n".join(
            [
                "My SKILL.md full context:",
                f"skill_hash: {skill_hash}",
                skill_text[:12_288],
            ]
        )
    persistent_context = "\n".join(
        [
            "My persistent organism context.",
            "",
            skill_section,
            "",
            "My memory.md:",
            memory_text[:1024],
        ]
    )
    stable_self_context = "\n\n".join([SELF_CHARTER, SELF_ECOLOGY_CONTEXT])
    history = [
        {"role": str(item.get("role")), "content": str(item.get("content"))[:1200]}
        for item in (dialogue_history or [])
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": stable_self_context},
        {"role": "assistant", "content": persistent_context},
        *history[-6:],
        {"role": "user", "content": current_user},
    ]


def build_action_prompt(skill_text: str, observation: Dict[str, Any]) -> str:
    messages = build_action_messages(skill_text, observation)
    lines: List[str] = []
    for message in messages:
        lines.extend([f"{message['role'].upper()}:", message["content"], ""])
    return "\n".join(lines)
