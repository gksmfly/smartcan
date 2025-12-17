# app/api/v1/recipes.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.recipe import RecipeCreate, RecipeOut, RecipeUpdate
from app.services import recipes_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def create_recipe_endpoint(
    data: RecipeCreate,
    db: Session = Depends(get_db),
):
    return recipes_service.create_recipe(db, data)


@router.get("/", response_model=List[RecipeOut])
def list_recipes_endpoint(
    db: Session = Depends(get_db),
):
    return recipes_service.list_recipes(db)


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe_endpoint(
    recipe_id: int,
    db: Session = Depends(get_db),
):
    recipe = recipes_service.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.patch("/{recipe_id}", response_model=RecipeOut)
def update_recipe_endpoint(
    recipe_id: int,
    data: RecipeUpdate,
    db: Session = Depends(get_db),
):
    recipe = recipes_service.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipes_service.update_recipe(db, recipe, data)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_endpoint(
    recipe_id: int,
    db: Session = Depends(get_db),
):
    recipe = recipes_service.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipes_service.delete_recipe(db, recipe)
    return