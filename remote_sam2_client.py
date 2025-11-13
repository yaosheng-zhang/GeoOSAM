"""
Remote SAM2 API Client
Support for using remote SAM2 model server for segmentation
"""

import sys
import os

# Fix for QGIS environment where sys.stderr/stdout might be None
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')

import json
import base64
import requests
import numpy as np
from io import BytesIO
from PIL import Image
from typing import Tuple, Optional, List
import time


class RemoteSAM2Client:
    """Client for remote SAM2 inference server"""

    def __init__(self, server_url: str, timeout: int = 300, max_retries: int = 3):
        """
        Initialize remote SAM2 client

        Args:
            server_url: Base URL of remote SAM2 server (e.g., "http://example.com:8000")
            timeout: Request timeout in seconds (default: 300)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'GeoOSAM-Client/1.0'
        })

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to remote server

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            response = self.session.get(
                f"{self.server_url}/health",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return True, f"Connected: {data.get('status', 'OK')}"
            else:
                return False, f"Server returned status {response.status_code}"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def _encode_image(self, image: np.ndarray) -> str:
        """
        Encode numpy image array to base64 string

        Args:
            image: numpy array (H, W, C) in uint8 format

        Returns:
            Base64 encoded string
        """
        # Convert numpy array to PIL Image
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)

        # Ensure RGB format
        if len(image.shape) == 2:
            image = np.stack([image] * 3, axis=-1)
        elif image.shape[-1] > 3:
            # For multispectral, use first 3 bands
            image = image[:, :, :3]

        pil_image = Image.fromarray(image)

        # Encode to PNG bytes
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG', compress_level=6)
        buffer.seek(0)

        # Encode to base64
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return img_base64

    def _decode_mask(self, mask_base64: str) -> np.ndarray:
        """
        Decode base64 mask string to numpy array

        Args:
            mask_base64: Base64 encoded mask string

        Returns:
            numpy array (H, W) in uint8 format
        """
        mask_bytes = base64.b64decode(mask_base64)
        mask_image = Image.open(BytesIO(mask_bytes))
        mask_array = np.array(mask_image)

        # Ensure binary mask
        if len(mask_array.shape) == 3:
            mask_array = mask_array[:, :, 0]

        return mask_array.astype(np.uint8)

    def predict(
        self,
        image: np.ndarray,
        point_coords: Optional[np.ndarray] = None,
        point_labels: Optional[np.ndarray] = None,
        box: Optional[np.ndarray] = None,
        multimask_output: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run SAM2 prediction on remote server

        Args:
            image: Input image array (H, W, C)
            point_coords: Point coordinates array (N, 2)
            point_labels: Point labels array (N,)
            box: Bounding box array (4,) in format [x1, y1, x2, y2]
            multimask_output: Whether to output multiple masks

        Returns:
            Tuple of (masks, scores, logits)
            - masks: (N, H, W) bool array
            - scores: (N,) float array
            - logits: (N, H, W) float array (placeholder, will be None for remote)
        """
        # Encode image
        image_base64 = self._encode_image(image)

        # Prepare request data
        request_data = {
            'image': image_base64,
            'multimask_output': multimask_output
        }

        # Add prompts
        if point_coords is not None and point_labels is not None:
            request_data['point_coords'] = point_coords.tolist()
            request_data['point_labels'] = point_labels.tolist()

        if box is not None:
            # Ensure box is correct format and doesn't contain NaN/inf
            box_array = np.array(box)

            # Flatten if box is 2D (e.g., [[x1, y1, x2, y2]])
            if box_array.ndim == 2:
                box_array = box_array.flatten()

            box_list = box_array.tolist()

            # Validate box values
            if len(box_list) != 4:
                raise ValueError(f"Box must have 4 values, got {len(box_list)}. Box shape: {np.array(box).shape}, Box content: {box}")

            # Check for NaN or inf
            import math
            for i, val in enumerate(box_list):
                if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                    raise ValueError(f"Box value at index {i} is invalid: {val}")

            # Convert to float to ensure JSON serialization
            request_data['box'] = [float(v) for v in box_list]

            print(f"🔍 Debug: Sending box to remote server: {request_data['box']}")

        # Make request with retry
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    f"{self.server_url}/predict",
                    json=request_data,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()

                    # Decode masks
                    masks_list = []
                    for mask_base64 in result['masks']:
                        mask = self._decode_mask(mask_base64)
                        masks_list.append(mask)

                    masks = np.array(masks_list)
                    scores = np.array(result['scores'])

                    # Note: logits are not returned for remote API (too large)
                    # Return None as placeholder
                    logits = None

                    return masks, scores, logits

                elif response.status_code == 500:
                    error_msg = response.json().get('error', 'Server error')
                    raise Exception(f"Server error: {error_msg}")
                elif response.status_code == 422:
                    # Validation error - get detailed error message
                    try:
                        error_detail = response.json()
                        raise Exception(f"Validation error (422): {error_detail}")
                    except:
                        raise Exception(f"Validation error (422): Invalid request format")
                else:
                    # Try to get error details
                    try:
                        error_detail = response.json()
                        raise Exception(f"Request failed with status {response.status_code}: {error_detail}")
                    except:
                        raise Exception(f"Request failed with status {response.status_code}")

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⚠️ Request timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception("Request timeout after all retries")

            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️ Connection error, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Connection error after all retries: {str(e)}")

            except Exception as e:
                if attempt < self.max_retries - 1 and "timeout" in str(e).lower():
                    wait_time = 2 ** attempt
                    print(f"⚠️ Error occurred, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise

        raise Exception("Prediction failed after all retries")


class RemoteSAM2Predictor:
    """
    Wrapper class to make RemoteSAM2Client compatible with local SAM2ImagePredictor API
    """

    def __init__(self, client: RemoteSAM2Client):
        """
        Initialize predictor wrapper

        Args:
            client: RemoteSAM2Client instance
        """
        self.client = client
        self._current_image = None

    def set_image(self, image: np.ndarray):
        """
        Set current image for prediction

        Args:
            image: Input image array (H, W, C)
        """
        self._current_image = image

    def predict(
        self,
        point_coords: Optional[np.ndarray] = None,
        point_labels: Optional[np.ndarray] = None,
        box: Optional[np.ndarray] = None,
        multimask_output: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run prediction on current image

        Args:
            point_coords: Point coordinates array (N, 2)
            point_labels: Point labels array (N,)
            box: Bounding box array (4,) in format [x1, y1, x2, y2]
            multimask_output: Whether to output multiple masks

        Returns:
            Tuple of (masks, scores, logits)
        """
        if self._current_image is None:
            raise RuntimeError("No image set. Call set_image() first.")

        return self.client.predict(
            image=self._current_image,
            point_coords=point_coords,
            point_labels=point_labels,
            box=box,
            multimask_output=multimask_output
        )

    def reset_image(self):
        """Reset current image"""
        self._current_image = None
