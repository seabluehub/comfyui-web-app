from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CharacterOut(BaseModel):
    id: int
    name: str
    code: str
    default_lora: str
    trigger_words: str
    base_model: str
    description: Optional[str] = None
    created_at: str
    avatar_icon: Optional[str] = "👧"
    negative_prompt: Optional[str] = ""
    lora_strength: Optional[float] = 0.85
    task_count: int = 0
    generated_count: int = 0

class CharacterCreate(BaseModel):
    name: str
    code: str
    trigger_words: str
    default_lora: Optional[str] = ""
    base_model: str = "sdxl"
    description: Optional[str] = None
    avatar_icon: Optional[str] = "👧"
    negative_prompt: Optional[str] = ""
    lora_strength: Optional[float] = 0.85
    auto_generate_matrix: bool = True

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    trigger_words: Optional[str] = None
    default_lora: Optional[str] = None
    base_model: Optional[str] = None
    description: Optional[str] = None
    avatar_icon: Optional[str] = None
    negative_prompt: Optional[str] = None
    lora_strength: Optional[float] = None

class CharacterPreset(BaseModel):
    name: str
    code: str
    avatar_icon: str
    trigger_words: str
    negative_prompt: str
    default_lora: str
    lora_strength: float
    base_model: str
    description: str
    style_hint: str

class ConsistencyBenchmarkRequest(BaseModel):
    character_id: int = 1
    style_tag: str = "ghibli"
    outfit_tag: str = "school_uniform"
    pose_tag: str = "portrait_close"
    seed: int = 424242
    checkpoint: Optional[str] = None

class ConsistencyBenchmarkPhaseItem(BaseModel):
    phase: int
    phase_name: str
    description: str
    prompt: str
    negative_prompt: str
    lora_used: Optional[str] = None
    lora_strength: float = 0.0
    image_url: Optional[str] = None
    status: str = "success"

class ConsistencyBenchmarkResponse(BaseModel):
    character_id: int
    character_name: str
    seed: int
    style_tag: str
    outfit_tag: str
    pose_tag: str
    phases: List[ConsistencyBenchmarkPhaseItem]

class ImageItem(BaseModel):
    id: int
    task_id: int
    character_id: int
    file_name: str
    image_url: str
    thumb_url: str
    file_size_bytes: int
    width: int
    height: int
    style_tag: Optional[str] = None
    outfit_tag: Optional[str] = None
    pose_tag: Optional[str] = None
    prompt_final: str
    seed: int
    rating: int = 0
    is_favorite: bool = False
    created_at: str
    gen_config: Optional[Dict[str, Any]] = None

class GalleryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    images: List[ImageItem]

class TagStat(BaseModel):
    tag: str
    count: int

class TagsResponse(BaseModel):
    styles: List[TagStat]
    outfits: List[TagStat]
    poses: List[TagStat]

class BatchStatusResponse(BaseModel):
    total: int
    pending: int
    running: int
    success: int
    failed: int
    is_active: bool
    is_paused: bool = False
    current_task_id: Optional[int] = None
    last_completed_image: Optional[str] = None
    progress_percent: float
    elapsed_time_sec: float
    avg_sec_per_img: float
    session_total: int = 0
    session_done: int = 0

class StartBatchRequest(BaseModel):
    character_id: int = 1
    model: str = "sdxl"                 # template selector: 'sdxl' or 'flux'
    steps: Optional[int] = None         # override sampling steps for selected tasks
    cfg: Optional[float] = None         # override cfg for selected tasks
    limit: Optional[int] = None         # max images to produce in this session
    width: Optional[int] = None         # override width for selected tasks
    height: Optional[int] = None        # override height for selected tasks
    # Selection filters (empty list or None = all)
    styles: Optional[List[str]] = None
    outfits: Optional[List[str]] = None
    poses: Optional[List[str]] = None
    include_done: bool = False          # re-run matched SUCCESS/FAILED tasks
    # Generation engine overrides
    checkpoint: Optional[str] = None    # checkpoint/unet filename; None = template default
    lora: Optional[str] = None          # None = character default, "" = disable lora, else filename
    lora_strength: Optional[float] = None

class SelectionPreviewResponse(BaseModel):
    matched: int
    pending: int
    success: int
    failed: int
    running: int

class RateImageRequest(BaseModel):
    rating: Optional[int] = Field(None, ge=0, le=5)
    is_favorite: Optional[bool] = None
