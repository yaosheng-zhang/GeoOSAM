"""
Remote SAM2 Inference Server Example

This is a sample implementation of a remote SAM2 inference server
that can be used with the GeoOSAM plugin.

Requirements:
    pip install fastapi uvicorn[standard] torch sam2 numpy pillow

Usage:
    python remote_server_example.py

    Or with custom host/port:
    uvicorn remote_server_example:app --host 0.0.0.0 --port 8000

API Endpoints:
    GET  /health          - Health check
    POST /predict         - Run SAM2 prediction
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import base64
import numpy as np
from PIL import Image
from io import BytesIO
import torch
import os
import sys

# Import SAM2
try:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from hydra import initialize_config_module
    from hydra.core.global_hydra import GlobalHydra
except ImportError:
    print("⚠️ SAM2 not found. Please install SAM2 following official instructions.")
    print("   https://github.com/facebookresearch/segment-anything-2")
    exit(1)


# ============= Configuration =============
CHECKPOINT_PATH = "sam2/checkpoints/sam2_hiera_large.pt"
MODEL_CONFIG = "sam2/sam2_hiera_l"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# =========================================


app = FastAPI(
    title="SAM2 Remote Inference Server",
    description="Remote inference server for Segment Anything Model 2",
    version="1.0.0"
)

# Enable CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global predictor instance
predictor = None


class PredictRequest(BaseModel):
    """Prediction request model"""
    image: str  # Base64 encoded image
    point_coords: Optional[List[List[float]]] = None  # [[x, y], ...]
    point_labels: Optional[List[int]] = None  # [1, 0, ...]
    box: Optional[List[float]] = None  # [x1, y1, x2, y2]
    multimask_output: bool = False


class PredictResponse(BaseModel):
    """Prediction response model"""
    masks: List[str]  # List of base64 encoded masks
    scores: List[float]  # Confidence scores


def initialize_model():
    """Initialize SAM2 model"""
    global predictor

    if predictor is not None:
        return

    print(f"🔧 Initializing SAM2 model on {DEVICE}...")
    print(f"   Config: {MODEL_CONFIG}")
    print(f"   Checkpoint: {CHECKPOINT_PATH}")

    try:
        # Add sam2 directory to Python path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sam2_dir = os.path.join(script_dir, "sam2")
        if sam2_dir not in sys.path:
            sys.path.insert(0, sam2_dir)

        # Initialize Hydra for SAM2 configs
        if GlobalHydra.instance().is_initialized():
            GlobalHydra.instance().clear()

        # Initialize Hydra globally (required by build_sam2)
        initialize_config_module(config_module="sam2.configs", version_base=None)

        # Build SAM2 model
        sam_model = build_sam2(MODEL_CONFIG, CHECKPOINT_PATH, device=DEVICE)

        if DEVICE == "cuda":
            sam_model = sam_model.cuda()

        sam_model.eval()

        # Create predictor
        predictor = SAM2ImagePredictor(sam_model)

        print(f"✅ SAM2 model loaded successfully on {DEVICE}")

    except Exception as e:
        print(f"❌ Failed to initialize model: {e}")
        import traceback
        print(traceback.format_exc())
        raise


@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    initialize_model()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "SAM2 Remote Inference Server",
        "version": "1.0.0",
        "status": "running",
        "device": DEVICE
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model": "SAM2",
        "device": DEVICE,
        "model_loaded": predictor is not None
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    Run SAM2 prediction

    Args:
        request: Prediction request with image and prompts

    Returns:
        PredictResponse with masks and scores
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not initialized")

    try:
        # Decode image from base64
        image_bytes = base64.b64decode(request.image)
        image_pil = Image.open(BytesIO(image_bytes))
        image_array = np.array(image_pil)

        # Ensure RGB format
        if len(image_array.shape) == 2:
            image_array = np.stack([image_array] * 3, axis=-1)
        elif image_array.shape[-1] == 4:
            # Remove alpha channel
            image_array = image_array[:, :, :3]

        # Set image
        predictor.set_image(image_array)

        # Prepare prompts
        point_coords = None
        point_labels = None
        box = None

        if request.point_coords and request.point_labels:
            point_coords = np.array(request.point_coords)
            point_labels = np.array(request.point_labels)

        if request.box:
            box = np.array(request.box)

        # Run prediction
        with torch.no_grad():
            masks, scores, logits = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=box,
                multimask_output=request.multimask_output
            )

        # Encode masks to base64
        encoded_masks = []
        for mask in masks:
            # Convert to uint8
            if mask.dtype != np.uint8:
                mask_uint8 = (mask * 255).astype(np.uint8)
            else:
                mask_uint8 = mask

            # Convert to PIL Image
            mask_pil = Image.fromarray(mask_uint8, mode='L')

            # Encode to PNG
            buffer = BytesIO()
            mask_pil.save(buffer, format='PNG')
            buffer.seek(0)

            # Encode to base64
            mask_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            encoded_masks.append(mask_base64)

        # Convert scores to list
        scores_list = scores.tolist() if hasattr(scores, 'tolist') else list(scores)

        return PredictResponse(
            masks=encoded_masks,
            scores=scores_list
        )

    except Exception as e:
        import traceback
        error_detail = f"Prediction failed: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🌐 Starting SAM2 Remote Inference Server")
    print("=" * 60)
    print(f"Device: {DEVICE}")
    print(f"Model: {MODEL_CONFIG}")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
