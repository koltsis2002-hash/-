"""RecommendationEngine: links each priority need to a protection direction and, only when verified,
to a documented product. Never invents a product to fill the presentation."""
from dataclasses import dataclass

from app.services.advisor.content import variant
from app.services.advisor.needs import AssessedNeed
from app.services.advisor.products import Catalog


@dataclass
class Recommendation:
    need: AssessedNeed
    direction: dict
    products: list

    @property
    def documented(self) -> bool:
        return bool(self.products)


def recommend(content, needs: list[AssessedNeed], catalog: Catalog, solo: bool = False) -> list[Recommendation]:
    return [
        Recommendation(
            need=n, direction=variant(content.directions[n.id], solo),
            products=catalog.for_category(content.directions[n.id]["category"]),
        )
        for n in needs if n.is_priority
    ]
