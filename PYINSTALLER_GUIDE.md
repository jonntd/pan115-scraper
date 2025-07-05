# PyInstaller 打包指南

本文档详细说明了如何使用PyInstaller将Pan115 Scraper打包为独立的可执行文件。

## 🔧 已解决的问题

### 1. 资源路径问题
**问题**: PyInstaller打包后，Flask无法找到templates和static文件夹。

**解决方案**: 
- 在`app.py`中添加了`get_resource_path()`函数
- 动态检测是否在PyInstaller环境中运行
- 正确设置Flask的`template_folder`和`static_folder`参数

```python
def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容PyInstaller打包"""
    try:
        base_path = sys._MEIPASS  # PyInstaller临时目录
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
```

### 2. 配置文件路径问题
**问题**: 配置文件`config.json`在打包后无法正确读写。

**解决方案**:
- 配置文件应该放在可执行文件同目录，而不是临时目录
- 添加了`get_config_path()`函数来动态获取配置文件路径

```python
def get_config_path():
    """获取配置文件路径，优先使用可执行文件同目录"""
    try:
        if hasattr(sys, '_MEIPASS'):
            exe_dir = os.path.dirname(sys.executable)
            return os.path.join(exe_dir, 'config.json')
        else:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    except:
        return 'config.json'
```

### 3. 日志文件路径问题
**解决方案**: 日志文件也应该放在可执行文件同目录。

### 4. 备份文件路径问题
**解决方案**: 重命名备份文件同样需要放在可执行文件同目录。

### 5. 隐藏导入问题
**解决方案**: 在`pan115-scraper.spec`中添加了完整的隐藏导入列表，包括：
- 加密相关模块
- Flask及其依赖
- 网络请求相关模块
- 标准库模块

## 📁 文件结构

```
pan115-scraper/
├── app.py                    # 主应用文件（已修复路径问题）
├── pan115-scraper.spec      # PyInstaller配置文件
├── hook-app.py              # PyInstaller hook文件
├── build.sh                 # Linux/macOS构建脚本
├── build-windows.ps1        # Windows构建脚本
├── build.bat                # Windows批处理构建脚本
├── test_build.py            # 构建测试脚本
├── start_packaged.py        # 打包版本启动脚本
├── templates/               # HTML模板
├── static/                  # 静态资源
├── config.json.example      # 配置文件示例
└── dist/                    # 构建输出目录
    ├── pan115-scraper-win.exe    # Windows可执行文件
    ├── pan115-scraper-mac        # macOS可执行文件
    └── pan115-scraper-linux      # Linux可执行文件
```

## 🚀 构建步骤

### 方法一：使用构建脚本

#### Windows
```powershell
# PowerShell脚本
.\build-windows.ps1

# 或批处理脚本
.\build.bat
```

#### Linux/macOS
```bash
# 设置执行权限
chmod +x build.sh

# 运行构建
./build.sh
```

### 方法二：手动构建

1. **安装依赖**
```bash
pip install pyinstaller
pip install -r requirements.txt
```

2. **运行PyInstaller**
```bash
pyinstaller pan115-scraper.spec
```

3. **测试构建结果**
```bash
python test_build.py
```

## 🧪 测试打包结果

### 自动测试
```bash
python test_build.py
```

### 手动测试
```bash
# 启动打包后的应用
python start_packaged.py

# 或直接运行可执行文件
./dist/pan115-scraper-mac  # macOS
./dist/pan115-scraper-linux  # Linux
.\dist\pan115-scraper-win.exe  # Windows
```

## ⚙️ 配置说明

### PyInstaller Spec文件关键配置

1. **数据文件包含**
```python
datas=[
    ('templates', 'templates'),
    ('static', 'static'),
    ('config.json.example', '.'),
    ('README.md', '.'),
    ('LICENSE', '.'),
],
```

2. **隐藏导入**
- 包含了所有必要的Python模块
- 特别注意加密、网络请求、Flask相关模块

3. **排除项**
- 排除了不必要的大型库（如numpy、matplotlib等）
- 减小可执行文件大小

4. **优化选项**
- 启用UPX压缩
- 优化级别设为1

## 🐛 常见问题

### 1. 模板文件找不到
**错误**: `TemplateNotFound: index.html`

**解决**: 确保`app.py`中正确设置了模板路径，并且spec文件包含了templates目录。

### 2. 静态文件404
**错误**: CSS/JS文件无法加载

**解决**: 确保Flask正确设置了static_folder路径。

### 3. 配置文件无法保存
**错误**: 配置更改后重启丢失

**解决**: 确保配置文件路径指向可执行文件同目录，而不是临时目录。

### 4. 导入错误
**错误**: `ModuleNotFoundError`

**解决**: 在spec文件的hiddenimports中添加缺失的模块。

### 5. 可执行文件过大
**解决**: 
- 检查excludes列表，排除不必要的库
- 启用UPX压缩
- 使用`--onefile`选项

## 📊 性能优化

1. **减小文件大小**
   - 排除不必要的库
   - 启用UPX压缩
   - 优化导入

2. **提高启动速度**
   - 减少隐藏导入
   - 优化代码结构
   - 使用lazy loading

3. **内存优化**
   - 避免全局变量
   - 及时释放资源
   - 使用生成器

## 🔍 调试技巧

1. **启用调试模式**
```python
# 在spec文件中设置
debug=True
```

2. **查看详细日志**
```bash
pyinstaller --log-level DEBUG pan115-scraper.spec
```

3. **分析依赖**
```bash
pyi-archive_viewer dist/pan115-scraper-mac
```

4. **测试导入**
```python
# 在Python中测试模块导入
import sys
sys.path.insert(0, 'dist/pan115-scraper-mac')
```

## 📝 注意事项

1. **路径分隔符**: 使用`os.path.join()`而不是硬编码路径分隔符
2. **编码问题**: 确保所有文件使用UTF-8编码
3. **权限问题**: 确保可执行文件有执行权限
4. **防病毒软件**: 某些防病毒软件可能误报，需要添加白名单
5. **依赖版本**: 确保所有依赖版本兼容

## 🎯 最佳实践

1. **版本控制**: 不要将dist目录提交到版本控制
2. **自动化构建**: 使用CI/CD自动化构建过程
3. **测试覆盖**: 每次构建后都要进行完整测试
4. **文档更新**: 及时更新构建文档和说明
5. **用户反馈**: 收集用户反馈，持续改进打包质量
