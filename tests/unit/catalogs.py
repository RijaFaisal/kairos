"""Sample catalogs for tests. Two unrelated kinds of business, so nothing in
the domain code can quietly depend on one."""

from kairos.domain.catalog import CatalogItem

FOOD = [
    CatalogItem(id=1, name="Chicken Dumplings", price=650, unit="plate of 8",
                aliases=("chicken", "chkn dumplings"), category="Dumplings"),
    CatalogItem(id=2, name="Beef Dumplings", price=750, unit="plate of 8",
                aliases=("beef",), category="Dumplings"),
    CatalogItem(id=3, name="Veg Spring Rolls", price=400, unit="plate of 6",
                aliases=("spring rolls", "rolls"), category="Sides"),
    CatalogItem(id=4, name="Mint Chutney", price=100, unit="cup",
                aliases=("chutney",), available=False, category="Sides"),
]

CLOTHING = [
    CatalogItem(id=101, name="Cotton Kurta", price=3500, unit="piece",
                aliases=("kurta",), category="Tops"),
    CatalogItem(id=102, name="Lawn Suit 3 Piece", price=6800, unit="suit",
                aliases=("lawn suit", "3 piece"), category="Suits"),
    CatalogItem(id=103, name="Silk Dupatta", price=2200, unit="piece",
                aliases=("dupatta",), category="Accessories"),
    CatalogItem(id=104, name="Khaddar Shawl", price=4500, unit="piece",
                aliases=("shawl",), category="Accessories"),
]
