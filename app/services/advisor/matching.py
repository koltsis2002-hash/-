"""Solutions shown on the «Τι λύσεις υπάρχουν για αυτά;» slide, one entry per priority need.

match_solutions is the single place to connect a reasoning engine later. It receives a
Recommendation (the assessed need, its protection direction and any verified products) and returns
what the slide lists for that need. Until then it returns only documented material: verified
products, or else the protection direction marked as an area to explore. Nothing is generated.
"""


def match_solutions(recommendation) -> list[dict]:
    direction = recommendation.direction
    if recommendation.products:
        return [{"title": p.name, "text": p.summary or direction["direction"], "documented": True}
                for p in recommendation.products]
    return [{"title": direction["title"], "text": direction["direction"], "documented": False}]
