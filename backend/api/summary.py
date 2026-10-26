"""Grounded facts for catch-up summaries, including historical windows.

The model selects evidence IDs, not numbers or prose. Every displayed sentence
is rendered from the corresponding source fact, not 'verified' by the model.
"""


def summary_facts(state, minute, window, joined_at):
    start = max(0, minute - 10) if window == "last-10" else (
        joined_at if window == "since-joined" else -1
    )
    events = [event for event in state["timeline"] if event["minute"] <= minute]
    selected = [event for event in events if event["minute"] > start]
    goals = [event for event in events if event["event_type"] in ("shot", "goal")
             and (event["event_type"] == "goal" or event["detail"].get("outcome") == "goal")]
    score = {"home": 0, "away": 0}
    for goal in goals:
        after = goal["detail"].get("score_after")
        if after:
            home, away = after.split("-")
            score = {"home": int(home), "away": int(away)}
        elif goal.get("side") in score:
            score[goal["side"]] += 1
    if minute == state["minute"]:
        score = state["score"]
    home = (state.get("home") or {}).get("name", "Home")
    away = (state.get("away") or {}).get("name", "Away")
    score_known = (minute == state["minute"] or len(state["timeline"]) < 300
                   or any(goal["detail"].get("score_after") for goal in goals))
    score_fact = (
        f"At {minute}′, the score is {home} {score['home']}–{score['away']} {away}."
        if score_known else
        f"The retained event history does not establish the score at {minute}′."
    )
    facts = {"score": score_fact}
    for event in selected:
        facts[f"event:{event['seq']}"] = f"{event['display']} — {event['label']}."
    if not selected:
        facts["quiet"] = "No events are available in the retained history for this time window."
    # Current aggregates are not historical snapshots or window deltas.
    if minute == state["minute"] and window == "since-kickoff":
        stats = state["stats"]
        facts["possession"] = (
            f"{home} have had {stats['possession']['home']}% of possession; "
            f"{away} have had {stats['possession']['away']}%."
        )
        facts["shots"] = (
            f"Shots: {home} {stats['shots']['home']}, {away} {stats['shots']['away']}."
        )
    if window == "last-10":
        title = f"The last ten minutes, to {minute}′"
    elif window == "since-joined":
        title = f"Since you joined at {joined_at}′" if joined_at <= minute else "Before you joined"
    else:
        title = f"The match so far, to {minute}′"
    # Prefer goals and the most recent decisions in the deterministic fallback.
    important = [f"event:{e['seq']}" for e in selected if e in goals]
    recent = [f"event:{e['seq']}" for e in selected[-3:]]
    defaults = list(dict.fromkeys(["score", *important, *recent,
                                  *(k for k in ("quiet", "possession", "shots") if k in facts)]))[:8]
    return title, facts, defaults
