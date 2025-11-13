# 延迟模型初始化和配置持久化修复

## 问题描述

即使启用远程服务器，插件启动时仍然会弹出要求下载本地模型的对话框。如果用户点击"否"，插件GUI无法打开。

## 根本原因

1. 在 `__init__` 中立即调用 `_init_sam_model()`
2. 此时 `use_remote_server` 是硬编码的 `False`
3. 用户的远程服务器配置没有被保存和恢复
4. 即使想用远程服务器，启动时也会尝试加载本地模型

## 解决方案

### 1. 配置持久化

使用 QGIS 的 `QSettings` 保存和恢复用户配置：

```python
# 在 __init__ 中加载配置
from qgis.PyQt.QtCore import QSettings
settings = QSettings()
self.use_remote_server = settings.value("GeoOSAM/use_remote_server", False, type=bool)
self.remote_server_url = settings.value("GeoOSAM/remote_server_url", "", type=str)
```

### 2. 延迟模型初始化

不在 `__init__` 中立即初始化模型：

```python
# 在 __init__ 中
self.predictor = None
self.model_initialized = False
# 不调用 self._init_sam_model()
```

### 3. 按需初始化

添加确保模型已初始化的函数：

```python
def _ensure_model_initialized(self):
    """Ensure model is initialized before use"""
    if not self.model_initialized:
        self.logger.log_info("Model not initialized yet, initializing now...")
        self._init_sam_model()
        self.model_initialized = True
```

在需要使用模型时调用：

```python
def _run_segmentation(self):
    # Ensure model is initialized before running segmentation
    try:
        self._ensure_model_initialized()
    except Exception as e:
        self._update_status(f"❌ Failed to initialize model: {str(e)}", "error")
        return
    # ... 继续分割逻辑
```

### 4. 保存用户选择

当用户修改设置时自动保存：

```python
def _on_remote_server_toggle(self, checked):
    self.use_remote_server = checked
    # Save setting
    settings = QSettings()
    settings.setValue("GeoOSAM/use_remote_server", checked)
    # ...

def _test_remote_connection(self):
    self.remote_server_url = url
    # Save setting
    settings = QSettings()
    settings.setValue("GeoOSAM/remote_server_url", url)
    # ...
```

## 修改的代码位置

### 1. `geo_osam_dialog.py:1242-1267` - `__init__` 函数

**修改前**：
```python
def __init__(self, iface, parent=None):
    # ...
    self.use_remote_server = False
    self.remote_server_url = ""
    self.remote_client = None

    self._init_sam_model()  # 立即初始化
```

**修改后**：
```python
def __init__(self, iface, parent=None):
    # ...
    # Load settings from QSettings
    from qgis.PyQt.QtCore import QSettings
    settings = QSettings()
    self.use_remote_server = settings.value("GeoOSAM/use_remote_server", False, type=bool)
    self.remote_server_url = settings.value("GeoOSAM/remote_server_url", "", type=str)
    self.remote_client = None

    # Predictor will be initialized later when needed
    self.predictor = None
    self.model_initialized = False
```

### 2. `geo_osam_dialog.py:1323-1343` - 新增函数

```python
def _ensure_model_initialized(self):
    """Ensure model is initialized before use"""
    if not self.model_initialized:
        self.logger.log_info("Model not initialized yet, initializing now...")
        self._init_sam_model()
        self.model_initialized = True
```

### 3. `geo_osam_dialog.py:2062-2085` - 远程服务器开关

**修改**：
- 添加 QSettings 保存
- 标记模型需要重新初始化而不是立即初始化

```python
def _on_remote_server_toggle(self, checked):
    from qgis.PyQt.QtCore import QSettings

    self.use_remote_server = checked
    # Save setting
    settings = QSettings()
    settings.setValue("GeoOSAM/use_remote_server", checked)

    if checked:
        self._update_status("🌐 Remote server mode enabled", "info")
    else:
        self._update_status("💻 Local model mode enabled", "info")
        # Mark model as needing reinitialization
        if self.model_initialized:
            self.model_initialized = False
```

### 4. `geo_osam_dialog.py:2087-2126` - 测试远程连接

**修改**：
- 添加 QSettings 保存 URL
- 连接成功后标记需要重新初始化

```python
def _test_remote_connection(self):
    from qgis.PyQt.QtCore import QSettings

    url = self.remoteServerUrlInput.text().strip()
    self.remote_server_url = url

    # Save setting
    settings = QSettings()
    settings.setValue("GeoOSAM/remote_server_url", url)

    # Test connection
    if success:
        # Mark model as needing reinitialization
        self.model_initialized = False
```

### 5. `geo_osam_dialog.py:2613-2620` - 分割函数

**修改**：
- 在运行分割前确保模型已初始化

```python
def _run_segmentation(self):
    """Enhanced segmentation that ensures current layer is used"""
    # Ensure model is initialized before running segmentation
    try:
        self._ensure_model_initialized()
    except Exception as e:
        self._update_status(f"❌ Failed to initialize model: {str(e)}", "error")
        return
    # ...
```

## 使用流程

### 首次使用（远程模式）

1. 启动QGIS，加载GeoOSAM插件
2. **插件GUI正常打开，不会弹出下载对话框** ✅
3. 在"Model Settings"中：
   - 开启"Use Remote Server"
   - 输入服务器URL
   - 点击"Test Connection"
4. 配置自动保存
5. 点击地图选择区域并运行分割
6. **此时才初始化远程模型** ✅

### 再次使用

1. 启动QGIS，加载GeoOSAM插件
2. **自动加载上次的配置**（远程服务器开启）
3. **插件GUI正常打开，不会弹出下载对话框** ✅
4. 直接使用，无需重新配置

### 首次使用（本地模式）

1. 启动QGIS，加载GeoOSAM插件
2. **插件GUI正常打开** ✅
3. 点击地图选择区域并运行分割
4. **此时才初始化本地模型** ✅
5. 如果checkpoint不存在，弹出下载对话框
6. 用户可以选择下载或取消

## 优势

### 1. 用户体验改善

- ✅ 不会在启动时强制检查/下载模型
- ✅ 远程模式下完全不需要本地模型
- ✅ 配置持久化，无需每次重新设置
- ✅ GUI可以正常打开，不会因为模型问题卡死

### 2. 性能优化

- ✅ 启动更快（不加载模型）
- ✅ 只在需要时才初始化
- ✅ 避免不必要的模型加载

### 3. 灵活性

- ✅ 可以先配置再使用
- ✅ 可以随时切换本地/远程模式
- ✅ 配置自动保存和恢复

## 配置存储位置

配置保存在 QGIS 的 QSettings 中：

**Windows**: `HKEY_CURRENT_USER\Software\QGIS\QGIS3`

**Linux**: `~/.config/QGIS/QGIS3.ini`

**macOS**: `~/Library/Preferences/org.qgis.qgis3.plist`

**配置键**：
- `GeoOSAM/use_remote_server`: bool
- `GeoOSAM/remote_server_url`: string

## 测试步骤

### 测试1: 远程模式启动

1. 重启QGIS
2. 在插件管理器中启用GeoOSAM
3. **期望**: 插件GUI立即打开，无弹窗
4. 配置远程服务器并测试连接
5. 运行分割
6. **期望**: 使用远程模型，无需下载本地模型

### 测试2: 配置持久化

1. 配置远程服务器
2. 重启QGIS
3. 再次打开GeoOSAM
4. **期望**: 远程服务器配置自动加载

### 测试3: 本地模式延迟加载

1. 禁用远程服务器
2. 重启QGIS
3. 打开GeoOSAM
4. **期望**: GUI正常打开
5. 运行分割
6. **期望**: 此时才检查/下载本地模型

## 注意事项

1. 如果远程服务器配置不正确，分割时会报错并回退到本地模型
2. 配置保存在QGIS设置中，卸载插件不会删除配置
3. 可以手动清除配置：设置 → 选项 → 高级 → 编辑设置 → 删除 GeoOSAM 相关键

## 总结

通过延迟模型初始化和配置持久化，完全解决了：
- ✅ 启动时强制检查本地模型的问题
- ✅ 远程模式需要本地checkpoint的问题
- ✅ 配置不保存需要重复设置的问题
- ✅ 点击"否"后GUI无法打开的问题

用户现在可以：
- 在远程模式下完全不需要本地模型
- 启动插件后再决定使用哪种模式
- 配置自动保存，无需重复设置
