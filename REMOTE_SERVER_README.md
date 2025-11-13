# GeoOSAM Remote Server Feature

This document explains how to use the remote SAM2 server feature in GeoOSAM.

## Overview

The remote server feature allows you to offload SAM2 model inference to a remote server, which is useful when:

- Your local machine doesn't have enough GPU memory
- You want to centralize model hosting for multiple users
- You need to use a more powerful GPU remotely
- You want to reduce local resource usage

## Architecture

```
GeoOSAM Plugin (QGIS)  →  Remote SAM2 Server  →  SAM2 Model
     (Client)                (FastAPI)              (GPU/CPU)
```

## Setup Instructions

### 1. Set Up Remote Server

#### Requirements
```bash
pip install fastapi uvicorn[standard] torch sam2 numpy pillow
```

#### Download SAM2 Checkpoint
```bash
cd /path/to/plugin/GeoOSAM
mkdir -p checkpoints
cd checkpoints
wget https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2.1_hiera_tiny.pt
```

#### Start the Server
```bash
cd /path/to/plugin/GeoOSAM
python remote_server_example.py
```

Or with custom configuration:
```bash
uvicorn remote_server_example:app --host 0.0.0.0 --port 8000
```

The server will start at `http://0.0.0.0:8000`

#### Configuration Options

Edit `remote_server_example.py` to customize:

```python
# Model configuration
CHECKPOINT_PATH = "checkpoints/sam2.1_hiera_tiny.pt"
MODEL_CONFIG = "sam2.1/sam2.1_hiera_t"
DEVICE = "cuda"  # or "cpu"

# Server configuration (in main)
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Configure GeoOSAM Plugin

1. Open QGIS and load GeoOSAM plugin
2. In the Control Panel, find "Model Settings" section
3. Toggle "Use Remote Server" switch
4. Enter your server URL (e.g., `http://192.168.1.100:8000`)
5. Click "Test Connection" to verify
6. Start using segmentation as normal!

## API Specification

### Health Check
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "model": "SAM2",
  "device": "cuda",
  "model_loaded": true
}
```

### Prediction
```http
POST /predict
Content-Type: application/json
```

Request body:
```json
{
  "image": "base64_encoded_png_image",
  "point_coords": [[x1, y1], [x2, y2]],  // optional
  "point_labels": [1, 0],                 // optional
  "box": [x1, y1, x2, y2],               // optional
  "multimask_output": false
}
```

Response:
```json
{
  "masks": ["base64_mask1", "base64_mask2"],
  "scores": [0.95, 0.87]
}
```

## Advanced Configuration

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN pip install fastapi uvicorn[standard] pillow

# Install SAM2 (follow official instructions)
RUN git clone https://github.com/facebookresearch/segment-anything-2.git && \
    cd segment-anything-2 && \
    pip install -e .

# Copy server code
COPY remote_server_example.py /app/
COPY checkpoints /app/checkpoints

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "remote_server_example:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t sam2-server .
docker run -d -p 8000:8000 --gpus all sam2-server
```

### NGINX Reverse Proxy

For production deployment with HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

### Multiple Model Support

Modify server to support different models:

```python
MODELS = {
    "tiny": ("sam2.1/sam2.1_hiera_t", "checkpoints/sam2.1_hiera_tiny.pt"),
    "large": ("sam2.1/sam2.1_hiera_l", "checkpoints/sam2.1_hiera_large.pt")
}

class PredictRequest(BaseModel):
    image: str
    model: str = "tiny"  # Add model selection
    # ... other fields
```

## Troubleshooting

### Connection Failed

1. **Check firewall**: Ensure port 8000 is open
   ```bash
   sudo ufw allow 8000
   ```

2. **Check server is running**:
   ```bash
   curl http://your-server:8000/health
   ```

3. **Check network connectivity**:
   ```bash
   ping your-server
   ```

### Slow Performance

1. **Use GPU**: Ensure CUDA is available and `DEVICE = "cuda"`
2. **Increase timeout**: Edit `remote_sam2_client.py`:
   ```python
   RemoteSAM2Client(server_url, timeout=600)  # 10 minutes
   ```
3. **Use smaller images**: Large images take longer to encode/decode

### Out of Memory

1. **Use smaller model**: Switch to `sam2.1_hiera_tiny.pt`
2. **Reduce batch size**: Process images one at a time
3. **Add memory monitoring**:
   ```python
   print(f"GPU Memory: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
   ```

## Performance Benchmarks

Typical performance on different setups:

| Setup | Device | Model | Time/Image |
|-------|--------|-------|------------|
| Local | RTX 3090 | Tiny | ~0.5s |
| Remote (LAN) | RTX 3090 | Tiny | ~1.2s |
| Remote (WAN) | V100 | Large | ~3.5s |
| Local | CPU (16 cores) | Tiny | ~8s |

Network overhead: ~0.5-1s for image encoding/decoding

## Security Considerations

⚠️ **Important**: The example server has no authentication!

For production use:

1. **Add API key authentication**:
   ```python
   from fastapi import Header, HTTPException

   async def verify_token(x_api_key: str = Header()):
       if x_api_key != "your-secret-key":
           raise HTTPException(status_code=401, detail="Invalid API key")

   @app.post("/predict", dependencies=[Depends(verify_token)])
   async def predict(request: PredictRequest):
       # ...
   ```

2. **Use HTTPS** with valid SSL certificates
3. **Rate limiting** to prevent abuse
4. **Input validation** for image size and format
5. **Run behind firewall** or VPN for private networks

## Client Configuration Options

In `remote_sam2_client.py`:

```python
client = RemoteSAM2Client(
    server_url="http://your-server:8000",
    timeout=300,        # Request timeout (seconds)
    max_retries=3       # Retry attempts on failure
)
```

## Support

For issues or questions:
- Check server logs: `journalctl -u sam2-server -f`
- Enable debug mode in QGIS Python console
- Report issues on GitHub

## License

This remote server feature follows the same license as GeoOSAM and SAM2.
