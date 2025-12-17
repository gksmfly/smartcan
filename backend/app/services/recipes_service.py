# app/services/recipes_service.py

from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models.recipe import Recipe
from app.schemas.recipe import RecipeCreate, RecipeUpdate


def create_recipe(db: Session, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        sku_id=data.sku_id,
        name=data.name,
        target_amount=data.target_amount,
        base_valve_ms=data.base_valve_ms,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def get_recipe_by_id(db: Session, recipe_id: int) -> Optional[Recipe]:
    return db.get(Recipe, recipe_id)


def get_recipe_by_sku_id(db: Session, sku_id: str) -> Optional[Recipe]:
    stmt = select(Recipe).where(Recipe.sku_id == sku_id).limit(1)
    return db.scalars(stmt).first()


def list_recipes(db: Session) -> List[Recipe]:
    stmt = select(Recipe).order_by(Recipe.id)
    return list(db.scalars(stmt))


def update_recipe(db: Session, recipe: Recipe, data: RecipeUpdate) -> Recipe:
    for field, value in data.dict(exclude_unset=True).items():
        setattr(recipe, field, value)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def delete_recipe(db: Session, recipe: Recipe) -> None:
    db.delete(recipe)
    db.commit()