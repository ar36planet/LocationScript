import json

import storage
from core.result import Result


def list_favorites() -> Result:
    try:
        favorites = storage.load_favorites()
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to read favorites: {e}")
    return Result(True, "OK", f"{len(favorites)} favorite(s) loaded", data={"favorites": favorites})


def add_favorite(name, lat, lng) -> Result:
    name = (name or "").strip()
    if not name:
        return Result(False, "PARAM_ERROR", "Name cannot be empty")
    try:
        float(lat)
        float(lng)
    except (TypeError, ValueError):
        return Result(False, "PARAM_ERROR", "Invalid lat/lng format")

    try:
        favorites = storage.load_favorites()
        favorites[name] = {"lat": str(lat), "lng": str(lng)}
        storage.save_favorites(favorites)
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to save favorite: {e}")
    return Result(True, "FAVORITE_ADDED", f"Favorite added: {name}")


def delete_favorite(name) -> Result:
    name = (name or "").strip()
    if not name:
        return Result(False, "PARAM_ERROR", "Name cannot be empty")

    try:
        favorites = storage.load_favorites()
        if name not in favorites:
            return Result(False, "PARAM_ERROR", f"Favorite not found: {name}")
        del favorites[name]
        storage.save_favorites(favorites)
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to delete favorite: {e}")
    return Result(True, "FAVORITE_DELETED", f"Favorite deleted: {name}")


def import_favorites(filepath) -> Result:
    if not filepath:
        return Result(False, "PARAM_ERROR", "File path is required")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to read file: {e}")

    imported = {}
    if isinstance(data, dict):
        for name, coords in data.items():
            if isinstance(coords, dict) and "lat" in coords and "lng" in coords:
                imported[name] = {"lat": str(coords["lat"]), "lng": str(coords["lng"])}
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "lat" in item and "lng" in item:
                name = item.get("name", f"{item['lat']}, {item['lng']}")
                imported[name] = {"lat": str(item["lat"]), "lng": str(item["lng"])}

    if not imported:
        return Result(False, "PARAM_ERROR", "No valid locations found in file")

    try:
        favorites = storage.load_favorites()
        favorites.update(imported)
        storage.save_favorites(favorites)
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to write favorites: {e}")

    return Result(True, "FAVORITES_IMPORTED", f"Imported {len(imported)} location(s)", data={"favorites": imported})
