from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
import json
from app.database import get_db
from app.models import GalleryResponse, ImageItem, TagsResponse, TagStat, RateImageRequest, CharacterOut

router = APIRouter(prefix="/api/gallery", tags=["Gallery"])

def _parse_gen_config(raw) -> Optional[dict]:
    """Parse the persisted generation-config JSON (template/checkpoint/lora/sampler)."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def _to_image_item(d: dict) -> ImageItem:
    return ImageItem(
        id=d["id"],
        task_id=d["task_id"],
        character_id=d["character_id"],
        file_name=d["file_name"],
        image_url=f"/output/full/{d['file_name']}",
        thumb_url=f"/output/thumbs/{d['file_name']}",
        file_size_bytes=d["file_size_bytes"],
        width=d["width"],
        height=d["height"],
        style_tag=d["style_tag"],
        outfit_tag=d["outfit_tag"],
        pose_tag=d["pose_tag"],
        prompt_final=d["prompt_final"],
        seed=d["seed"],
        rating=d["rating"] or 0,
        is_favorite=bool(d["is_favorite"]),
        created_at=str(d["created_at"]),
        gen_config=_parse_gen_config(d.get("gen_config"))
    )

@router.get("/character", response_model=CharacterOut)
def get_current_character(character_id: int = 1):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")
        return dict(row)

@router.get("/tags", response_model=TagsResponse)
def get_tags(character_id: int = 1):
    with get_db() as conn:
        cur = conn.cursor()

        def fetch_counts(field: str):
            cur.execute(f"""
                SELECT {field}, COUNT(*) as c FROM generated_images
                WHERE character_id = ? AND {field} IS NOT NULL
                GROUP BY {field} ORDER BY c DESC
            """, (character_id,))
            return [TagStat(tag=r[0], count=r[1]) for r in cur.fetchall()]

        return TagsResponse(
            styles=fetch_counts("style_tag"),
            outfits=fetch_counts("outfit_tag"),
            poses=fetch_counts("pose_tag")
        )

@router.get("/images", response_model=GalleryResponse)
def get_images(
    character_id: int = 1,
    style: Optional[str] = None,
    outfit: Optional[str] = None,
    pose: Optional[str] = None,
    rating_min: Optional[int] = None,
    is_favorite: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = Query("newest", enum=["newest", "oldest", "rating", "seed"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100)
):
    with get_db() as conn:
        cur = conn.cursor()
        conditions = ["character_id = ?"]
        params = [character_id]

        if style:
            conditions.append("style_tag = ?")
            params.append(style)
        if outfit:
            conditions.append("outfit_tag = ?")
            params.append(outfit)
        if pose:
            conditions.append("pose_tag = ?")
            params.append(pose)
        if rating_min is not None:
            conditions.append("rating >= ?")
            params.append(rating_min)
        if is_favorite is not None:
            conditions.append("is_favorite = ?")
            params.append(1 if is_favorite else 0)
        if search:
            conditions.append("(prompt_final LIKE ? OR file_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_clause = " WHERE " + " AND ".join(conditions)

        # Count total
        cur.execute(f"SELECT COUNT(*) FROM generated_images {where_clause}", params)
        total = cur.fetchone()[0]

        # Sorting
        order_dict = {
            "newest": "id DESC",
            "oldest": "id ASC",
            "rating": "rating DESC, id DESC",
            "seed": "seed ASC"
        }
        order_clause = order_dict.get(sort_by, "id DESC")

        offset = (page - 1) * page_size
        query = f"""
            SELECT id, task_id, character_id, file_name, file_size_bytes,
                   width, height, style_tag, outfit_tag, pose_tag,
                   prompt_final, seed, rating, is_favorite, created_at, gen_config
            FROM generated_images {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """
        cur.execute(query, params + [page_size, offset])
        rows = cur.fetchall()

        items = [_to_image_item(dict(r)) for r in rows]

        return GalleryResponse(
            total=total,
            page=page,
            page_size=page_size,
            images=items
        )

@router.get("/images/{image_id}", response_model=ImageItem)
def get_image_detail(image_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM generated_images WHERE id = ?", (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Image not found")
        return _to_image_item(dict(row))

@router.post("/images/{image_id}/rate")
def rate_image(image_id: int, req: RateImageRequest):
    with get_db() as conn:
        cur = conn.cursor()
        updates = []
        params = []
        if req.rating is not None:
            updates.append("rating = ?")
            params.append(req.rating)
        if req.is_favorite is not None:
            updates.append("is_favorite = ?")
            params.append(1 if req.is_favorite else 0)

        if not updates:
            return {"status": "noop"}

        params.append(image_id)
        cur.execute(f"UPDATE generated_images SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return {"status": "ok", "image_id": image_id}
