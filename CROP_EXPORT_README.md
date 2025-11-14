# SAM分割对象裁剪图像导出功能说明

## 功能概述

在导出shapefile的同时，自动为每个分割对象生成：
- 1024×1024像素的裁剪图像（以对象bbox中心为中心）
- 对象bbox在裁剪图像中的相对坐标
- 详细的元数据信息（JSON格式）

## 使用方法

1. **进行SAM分割**：使用插件的点击或框选工具进行目标分割
2. **点击导出按钮**：在插件界面点击"Export"按钮
3. **自动生成输出**：系统会自动导出shapefile及裁剪图像

## 输出结构

导出后会在指定目录生成以下文件：

```
GeoOSAM_shapefiles/
├── SAM_Buildings_20250114_123456.shp          # Shapefile文件
├── SAM_Buildings_20250114_123456.shx          # Shapefile索引
├── SAM_Buildings_20250114_123456.dbf          # 属性数据
├── SAM_Buildings_20250114_123456.prj          # 投影信息
└── SAM_Buildings_20250114_123456_crops/       # 裁剪图像文件夹
    ├── feature_0000.png                       # 第1个对象的裁剪图像
    ├── feature_0001.png                       # 第2个对象的裁剪图像
    ├── feature_0002.png                       # 第3个对象的裁剪图像
    ├── ...
    └── bbox_info.json                         # 所有bbox信息
```

## bbox_info.json 格式说明

```json
[
  {
    "feature_id": 0,                              // 对象ID（与图像文件名对应）
    "image_file": "feature_0000.png",             // 裁剪图像文件名
    "bbox_crop_coords": [245, 312, 678, 789],     // bbox在裁剪图像中的坐标 [x_min, y_min, x_max, y_max]
    "bbox_width": 433,                            // bbox宽度（像素）
    "bbox_height": 477,                           // bbox高度（像素）
    "geo_bbox": {                                 // 原始地理坐标系bbox
      "xmin": 120.12345,
      "ymin": 30.67890,
      "xmax": 120.12456,
      "ymax": 30.67901
    },
    "center_geo": [120.124005, 30.678955],        // bbox中心点（地理坐标）
    "crop_size": 1024                             // 裁剪图像尺寸
  },
  ...
]
```

## 坐标系统说明

### 1. 裁剪图像坐标系（bbox_crop_coords）
- **原点**：裁剪图像左上角 (0, 0)
- **X轴**：向右递增（0 到 1024）
- **Y轴**：向下递增（0 到 1024）
- **格式**：[x_min, y_min, x_max, y_max]

### 2. 地理坐标系（geo_bbox）
- 使用原始栅格图层的坐标参考系统（CRS）
- 通常为经纬度（WGS84）或投影坐标系

## 裁剪逻辑

1. **中心点计算**：取对象bbox的几何中心
2. **裁剪区域**：以中心点为基准，截取1024×1024像素区域
3. **边界处理**：
   - 如果接近栅格边界，裁剪区域会自动调整
   - 不足1024×1024的区域会用黑色填充
4. **bbox转换**：将地理坐标bbox转换到裁剪图像坐标系

## 应用场景

### 1. 目标检测训练数据
```python
import json
from PIL import Image

# 读取bbox信息
with open('bbox_info.json', 'r') as f:
    data = json.load(f)

# 加载图像和bbox
for item in data:
    img = Image.open(item['image_file'])
    bbox = item['bbox_crop_coords']  # [x_min, y_min, x_max, y_max]

    # 转换为YOLO格式
    x_center = (bbox[0] + bbox[2]) / 2 / 1024
    y_center = (bbox[1] + bbox[3]) / 2 / 1024
    width = (bbox[2] - bbox[0]) / 1024
    height = (bbox[3] - bbox[1]) / 1024
```

### 2. 可视化验证
```python
import cv2
import json

# 读取数据
with open('bbox_info.json', 'r') as f:
    data = json.load(f)

# 在图像上绘制bbox
for item in data:
    img = cv2.imread(item['image_file'])
    bbox = item['bbox_crop_coords']

    # 绘制矩形框
    cv2.rectangle(img,
                  (bbox[0], bbox[1]),  # 左上角
                  (bbox[2], bbox[3]),  # 右下角
                  (0, 255, 0), 2)      # 绿色，线宽2

    cv2.imwrite(f"visualized_{item['image_file']}", img)
```

### 3. 转换为COCO格式
```python
import json

# 读取bbox信息
with open('bbox_info.json', 'r') as f:
    data = json.load(f)

# 构建COCO格式
coco_format = {
    "images": [],
    "annotations": [],
    "categories": [{"id": 1, "name": "object"}]
}

for idx, item in enumerate(data):
    # 图像信息
    coco_format["images"].append({
        "id": idx,
        "file_name": item['image_file'],
        "width": 1024,
        "height": 1024
    })

    # 标注信息
    bbox = item['bbox_crop_coords']
    coco_format["annotations"].append({
        "id": idx,
        "image_id": idx,
        "category_id": 1,
        "bbox": [bbox[0], bbox[1], bbox[2]-bbox[0], bbox[3]-bbox[1]],  # [x, y, width, height]
        "area": item['bbox_width'] * item['bbox_height'],
        "iscrowd": 0
    })

# 保存COCO格式
with open('annotations_coco.json', 'w') as f:
    json.dump(coco_format, f, indent=2)
```

## 注意事项

1. **栅格图层要求**：
   - 导出时需要有可用的栅格图层
   - 如果找不到栅格图层，只会导出shapefile，不会生成裁剪图像

2. **性能考虑**：
   - 大量对象（>100）可能需要较长处理时间
   - 建议分批次导出不同类别

3. **存储空间**：
   - 每个1024×1024 PNG图像约占用500KB-2MB
   - 100个对象约需50-200MB磁盘空间

4. **坐标精度**：
   - bbox坐标为整数像素坐标
   - 地理坐标保持原始精度

## 参数配置

当前默认参数：
- **crop_size**: 1024（可在`_export_all_classes`函数中修改）
- **export_crops**: True（自动导出裁剪图像）

如需修改裁剪尺寸，可在 `geo_osam_dialog.py` 的4092行修改：
```python
if self._export_layer_with_crops(layer, class_name, raster_layer,
                                  export_crops=True, crop_size=2048):  # 改为2048
```

## 技术细节

### 图像处理流程
1. 读取栅格图层RGB波段（支持多光谱自动转换）
2. 计算对象bbox中心点的像素坐标
3. 以中心点为基准提取crop_size×crop_size窗口
4. 归一化到0-255范围
5. 边界padding（如需要）

### 坐标转换
```python
# 地理坐标 -> 像素坐标
pixel_x, pixel_y = ~raster.transform * (geo_x, geo_y)

# 像素坐标 -> 裁剪图像坐标
crop_x = pixel_x - crop_window_x_min
crop_y = pixel_y - crop_window_y_min
```

## 问题排查

### 问题1：没有生成裁剪图像
- 检查是否有可用的栅格图层
- 查看QGIS Python控制台的日志输出

### 问题2：bbox坐标异常
- 确认栅格图层和分割结果在同一坐标系
- 检查分割对象是否在栅格范围内

### 问题3：图像全黑
- 检查栅格数据范围
- 确认分割对象位置正确

## 更新日志

**v1.0 (2025-01-14)**
- 初始版本
- 支持1024×1024裁剪图像导出
- 支持bbox坐标转换
- 支持JSON格式元数据
