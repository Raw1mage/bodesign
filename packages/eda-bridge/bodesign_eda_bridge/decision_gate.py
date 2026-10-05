"""Transport-neutral human decision gates, not automatic circuit approvals.

The caller supplies a synchronous ``ask_question(payload) -> option_id`` adapter.
No GUI, MCP transport, default answer, or persistence is implicitly selected.
"""

from copy import deepcopy


def _decide(topic, question, options, ask_question):
    if not callable(ask_question):
        raise ValueError("DECISION_CALLBACK_REQUIRED")
    if not isinstance(options, list) or len(options) < 2:
        raise ValueError("DECISION_OPTIONS_REQUIRED: at least two options")
    ids = []
    for option in options:
        if not isinstance(option, dict) or any(
            not isinstance(option.get(k), str) or not option[k].strip()
            for k in ("id", "label", "description")
        ):
            raise ValueError("DECISION_INVALID_OPTION")
        ids.append(option["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("DECISION_DUPLICATE_OPTION")
    payload = {"topic": topic, "question": question, "multiple": False,
               "options": deepcopy(options)}
    answer = ask_question(deepcopy(payload))
    if not isinstance(answer, str) or answer not in ids:
        raise ValueError(f"DECISION_INVALID_CHOICE: expected one of {ids!r}")
    return {"topic": topic, "status": "selected", "selected_id": answer,
            "selected_option": deepcopy(options[ids.index(answer)]),
            "provenance": {"channel": "injected_ask_question", "response": answer,
                           "identity_verified": False, "electrical_suitability": "not_verified"},
            "question": payload, "requires_engineering_validation": True}


def choose_power_architecture(ask_question):
    """Present qualitative tradeoffs; no device-specific performance is asserted."""
    return _decide("power_architecture", "Which regulator architecture should be evaluated?", [
        {"id": "ldo", "label": "LDO", "description":
         "Typically simpler and lower switching ripple; efficiency and heat depend on voltage drop. "
         "Compare total BOM cost and verify dissipation, dropout and noise from datasheets."},
        {"id": "buck", "label": "Buck", "description":
         "Can improve efficiency for larger step-down ratios; switching ripple and layout complexity "
         "require review. Compare inductor/BOM cost and device efficiency at the actual load."},
    ], ask_question)


def choose_passive_package(ask_question):
    return _decide("passive_package", "Choose an imperial passive package for review.", [
        {"id": "0402", "label": "0402 (imperial)", "description":
         "Most compact of these choices; more demanding hand soldering and rework. Verify ratings."},
        {"id": "0603", "label": "0603 (imperial)", "description":
         "Intermediate footprint and handling tradeoff; verify assembly capability and ratings."},
        {"id": "0805", "label": "0805 (imperial)", "description":
         "Largest of these choices, generally easier manual handling; consumes more board area. Verify ratings."},
    ], ask_question)


def choose_component_alternative(bom_options, ask_question):
    """Options require id, label, description and mpn; preserve supplied evidence.

    Selecting an MPN does not assert electrical or footprint interchangeability.
    """
    if not isinstance(bom_options, list) or any(
        not isinstance(o, dict) or not isinstance(o.get("mpn"), str) or not o["mpn"].strip()
        for o in bom_options
    ):
        raise ValueError("DECISION_MPN_REQUIRED")
    return _decide("component_alternative", "Which BOM alternative should be evaluated?",
                   deepcopy(bom_options), ask_question)
