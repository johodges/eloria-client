#!/usr/bin/env python3
"""Compile the unmodified server's recipe/item data for the Godot client."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    server_root = args.server_root.resolve()
    sys.path.insert(0, str(server_root))

    from eloria.items import (  # pylint: disable=import-outside-toplevel
        ITEMS,
        configure_items,
    )
    from eloria.knowledge import (  # pylint: disable=import-outside-toplevel
        infer_recipe_knowledge,
        load_books,
    )
    from eloria.recipes import load_recipes  # pylint: disable=import-outside-toplevel

    recipe_path = server_root / "config" / "recipes.txt"
    item_path = server_root / "config" / "items.txt"
    book_path = server_root / "config" / "books.txt"
    configure_items(item_path)
    recipes = load_recipes(recipe_path)
    books = load_books(str(book_path), ITEMS)

    knowledge_order = [
        book.knowledge for book in books.values() if not book.repeatable
    ]
    knowledge_indexes = {name: index for index, name in enumerate(knowledge_order)}
    names_by_image: dict[int, list[str]] = collections.defaultdict(list)
    for item in ITEMS.values():
        names_by_image[item.image_id].append(item.name)

    def item_definition(name: str, quantity: int = 1) -> dict[str, object]:
        item = ITEMS[name]
        aliases = names_by_image[item.image_id]
        return {
            "name": name,
            "quantity": quantity,
            "imageId": item.image_id,
            "ambiguousImage": len(aliases) > 1,
            "imageAliases": aliases if len(aliases) > 1 else [],
        }

    entries = []
    for index, recipe in enumerate(recipes):
        knowledge = recipe.knowledge or infer_recipe_knowledge(
            recipe.output, recipe.skill, books
        )
        if knowledge and knowledge not in knowledge_indexes:
            raise ValueError(f"missing knowledge index for {knowledge!r}")
        entries.append(
            {
                "id": index,
                "skill": recipe.skill,
                "output": recipe.output,
                "outputImageId": (
                    ITEMS[recipe.output].image_id if recipe.output in ITEMS else -1
                ),
                "level": recipe.level,
                "experience": recipe.experience,
                "food": recipe.food,
                "mana": recipe.mana,
                "knowledge": knowledge,
                "knowledgeIndex": knowledge_indexes.get(knowledge, -1),
                "ingredients": [
                    item_definition(name, quantity)
                    for name, quantity in recipe.ingredients
                ],
                "tools": [item_definition(name) for name in recipe.tools],
            }
        )

    document = {
        "schemaVersion": 1,
        "sources": {
            "recipesSha256": digest(recipe_path),
            "itemsSha256": digest(item_path),
            "booksSha256": digest(book_path),
        },
        "recipes": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} recipes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
