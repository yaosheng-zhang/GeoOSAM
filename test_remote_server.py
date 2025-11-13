"""
Simple test script for Remote SAM2 Server

This script helps you test if your remote SAM2 server is working correctly.

Usage:
    python test_remote_server.py http://your-server:8000
"""

import sys
import numpy as np
from PIL import Image
from remote_sam2_client import RemoteSAM2Client, RemoteSAM2Predictor


def create_test_image(width=512, height=512):
    """Create a simple test image"""
    # Create a simple test pattern: red circle on white background
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Draw a red circle
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 4

    y, x = np.ogrid[:height, :width]
    mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
    img[mask] = [255, 0, 0]  # Red

    return img


def test_connection(server_url):
    """Test connection to remote server"""
    print(f"\n{'='*60}")
    print(f"Testing Remote SAM2 Server: {server_url}")
    print(f"{'='*60}\n")

    try:
        # Create client
        print("1. Creating client...")
        client = RemoteSAM2Client(server_url, timeout=30, max_retries=2)

        # Test connection
        print("2. Testing connection...")
        success, message = client.test_connection()

        if not success:
            print(f"   ❌ Connection failed: {message}")
            return False

        print(f"   ✅ {message}")

        # Create test image
        print("\n3. Creating test image (512x512 with red circle)...")
        test_img = create_test_image()
        print(f"   ✅ Test image created: {test_img.shape}")

        # Test point prediction
        print("\n4. Testing point prediction...")
        point_coords = np.array([[256, 256]])  # Center of image
        point_labels = np.array([1])  # Foreground

        masks, scores, logits = client.predict(
            image=test_img,
            point_coords=point_coords,
            point_labels=point_labels,
            multimask_output=False
        )

        print(f"   ✅ Prediction successful!")
        print(f"      - Received {len(masks)} mask(s)")
        print(f"      - Mask shape: {masks[0].shape}")
        print(f"      - Scores: {scores}")

        # Test bbox prediction
        print("\n5. Testing bbox prediction...")
        box = np.array([128, 128, 384, 384])  # Box around circle

        masks, scores, logits = client.predict(
            image=test_img,
            box=box,
            multimask_output=True
        )

        print(f"   ✅ Prediction successful!")
        print(f"      - Received {len(masks)} mask(s)")
        print(f"      - Best score: {max(scores):.3f}")

        # Test with predictor wrapper
        print("\n6. Testing predictor wrapper API...")
        predictor = RemoteSAM2Predictor(client)
        predictor.set_image(test_img)

        masks, scores, logits = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels
        )

        print(f"   ✅ Predictor API works!")

        print(f"\n{'='*60}")
        print("🎉 All tests passed! Your remote server is working correctly.")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        print(f"\nTraceback:\n{traceback.format_exc()}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_remote_server.py <server_url>")
        print("Example: python test_remote_server.py http://localhost:8000")
        sys.exit(1)

    server_url = sys.argv[1]
    success = test_connection(server_url)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
