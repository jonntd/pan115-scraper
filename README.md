# Pan115 Scraper - 115云盘智能文件刮削器

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

**🚀 基于AI的115云盘智能文件管理和媒体刮削工具**

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置说明](#-配置说明) • [API文档](#-api文档) • [常见问题](#-常见问题)

</div>

---

## 📋 项目简介

Pan115 Scraper 是一个专为115云盘设计的智能文件管理工具，集成了AI驱动的智能分组、TMDB媒体信息刮削、批量重命名等功能。通过现代化的Web界面，让您的媒体文件管理变得简单高效。

### 🎯 核心优势

- **🤖 AI智能分组**: 基于AI的智能文件分组和命名
- **🎬 媒体信息刮削**: 集成TMDB数据库，自动获取电影/电视剧信息
- **⚡ 高性能处理**: 支持大量文件的批量处理和任务队列管理
- **🔒 安全可靠**: 本地部署，数据安全有保障
- **🌐 现代化界面**: 响应式Web界面，支持多设备访问

## ✨ 功能特性

### 🗂️ 文件管理
- **文件浏览**: 支持115云盘文件夹结构浏览
- **智能搜索**: 快速搜索和过滤文件
- **批量操作**: 支持批量重命名、移动、删除
- **统计分析**: 文件大小、类型分布统计

### 🤖 AI智能功能
- **智能分组**: AI自动识别和分组相关媒体文件
- **智能命名**: 基于内容特征生成标准化文件名
- **质量评估**: 评估文件名质量和分组合理性
- **任务队列**: 异步处理大量文件，支持进度跟踪

### 🎬 媒体刮削
- **TMDB集成**: 自动获取电影、电视剧元数据
- **多语言支持**: 支持中文、英文等多种语言



## 🚀 快速开始

### 环境要求

- Python 3.8+
- 115云盘账号和有效Cookie
- TMDB API密钥
- AI API密钥

### 安装方式

#### 方式一：源码运行

```bash
# 克隆项目
git clone https://github.com/jonntd/pan115-scraper.git
cd pan115-scraper

# 安装依赖
pip install -r requirements.txt

# 运行应用
python app.py
```

#### 方式二：预编译版本

从 [Releases](https://github.com/jonntd/pan115-scraper/releases) 页面下载对应平台的可执行文件：

- **Windows**: `pan115-scraper-win.exe`
- **Linux**: `pan115-scraper-linux`
- **macOS**: `pan115-scraper-mac`

### 首次配置

1. 启动应用后访问 http://localhost:5001
2. 点击右上角的"配置"按钮
3. 填入必要的配置信息：
   - **115云盘Cookie**: 从浏览器开发者工具获取
   - **TMDB API密钥**: 从 [TMDB官网](https://www.themoviedb.org/settings/api) 申请
   - **AI API配置**: 用于AI智能功能

## ⚙️ 配置说明

### 配置文件结构

应用使用 `config.json` 文件存储配置，主要配置项说明：

```json
{
    "QPS_LIMIT": 3,                    // API调用频率限制
    "CHUNK_SIZE": 50,                  // 批处理大小
    "MAX_WORKERS": 4,                  // 最大工作线程数
    "COOKIES": "your_115_cookies",     // 115云盘Cookie
    "TMDB_API_KEY": "your_tmdb_key",   // TMDB API密钥
    "AI_API_KEY": "your_ai_key",       // AI API密钥
    "AI_API_URL": "api_endpoint",      // AI API端点
    "MODEL": "gemini-model-name",      // AI模型名称
    "LANGUAGE": "zh-CN"                // 界面语言
}
```

### 重要配置项详解

#### 115云盘Cookie获取
1. 登录115云盘网页版
2. 打开浏览器开发者工具（F12）
3. 切换到Network标签
4. 刷新页面，找到任意请求
5. 复制Cookie字段的完整内容

#### TMDB API密钥申请
1. 注册 [TMDB账号](https://www.themoviedb.org/signup)
2. 前往 [API设置页面](https://www.themoviedb.org/settings/api)
3. 申请API密钥（选择Developer选项）
4. 复制API密钥到配置中

## 📚 使用指南

### 基础操作

1. **浏览文件**: 在主界面点击文件夹图标浏览115云盘文件
2. **智能分组**: 选择包含媒体文件的文件夹，点击"智能分组"
3. **查看结果**: 在任务列表中查看分组进度和结果
4. **批量重命名**: 根据分组结果进行批量重命名操作

### 高级功能

#### AI智能分组
- 自动识别电影、电视剧、动画等媒体类型
- 按系列、季度、年份等维度进行分组
- 生成标准化的文件夹名称和文件名

#### 任务队列管理
- 支持多个分组任务并发执行
- 实时进度跟踪和状态监控
- 任务取消和重试机制

#### 性能优化
- 智能QPS限制，避免API频率限制
- 批量处理大量文件
- 内存优化和错误恢复

## 🔌 API文档

### 核心API端点

#### 文件管理
- `GET /api/115/files` - 获取文件列表
- `GET /api/115/search` - 搜索文件
- `GET /api/115/stats` - 获取统计信息

#### 智能分组
- `POST /api/grouping_task/submit` - 提交分组任务
- `GET /api/grouping_task/status/<task_id>` - 获取任务状态
- `POST /api/grouping_task/cancel/<task_id>` - 取消任务

#### 系统管理
- `GET /api/health` - 健康检查
- `GET /api/config` - 获取配置
- `POST /api/save_config` - 保存配置

### API使用示例

```python
import requests

# 提交智能分组任务
response = requests.post('http://localhost:5001/api/grouping_task/submit',
                        data={'folder_id': '123456', 'folder_name': '电影文件夹'})
task_id = response.json()['task_id']

# 查询任务状态
status = requests.get(f'http://localhost:5001/api/grouping_task/status/{task_id}')
print(status.json())
```

## 🛠️ 开发指南

### 项目结构

```
pan115-scraper/
├── app.py                 # 主应用文件
├── config.json           # 配置文件
├── requirements.txt      # Python依赖
├── templates/           # HTML模板
│   └── index.html      # 主页面
├── static/             # 静态资源
│   ├── style.css      # 样式文件
│   └── script.js      # JavaScript文件
└── .github/           # GitHub Actions配置
    └── workflows/
        └── python-app.yml
```

### 核心模块

- **任务管理**: `GroupingTaskManager` - 智能分组任务队列管理
- **AI集成**: `call_ai_api()` - AI API调用和响应处理
- **文件处理**: `get_video_files_recursively()` - 递归文件扫描
- **性能监控**: `PerformanceMonitor` - API调用统计和监控

### 扩展开发

1. **添加新的AI模型支持**
2. **集成其他云盘服务**
3. **扩展媒体信息源**
4. **自定义分组规则**

## ❓ 常见问题

### Q: 为什么115云盘连接失败？
A: 请检查Cookie是否正确且未过期。Cookie通常有效期为几天到几周，需要定期更新。

### Q: AI分组功能不可用？
A: 请确保已正确配置AI API密钥和端点URL，并检查网络连接。

### Q: 处理大量文件时程序卡住？
A: 可以调整`QPS_LIMIT`和`CHUNK_SIZE`参数，降低并发度以避免API限制。

### Q: 如何备份配置？
A: 配置保存在`config.json`文件中，定期备份此文件即可。

### Q: 支持哪些媒体文件格式？
A: 支持常见的视频格式：mp4, mkv, avi, mov, wmv, flv, webm, m4v, 3gp, rmvb, ts, m2ts等。

### Q: 如何更新到最新版本？
A: 从GitHub Releases页面下载最新版本，或使用git pull更新源码。

## 🔧 故障排除

### 常见错误及解决方案

1. **端口5001被占用**
   ```bash
   # 查找占用端口的进程
   lsof -i :5001
   # 或者修改app.py中的端口号
   ```

2. **Cookie过期**
   - 重新登录115云盘获取新的Cookie
   - 在配置页面更新Cookie信息

3. **AI API调用失败**
   - 检查API密钥是否正确
   - 确认API端点URL可访问
   - 查看日志了解具体错误信息

## 📈 性能优化建议

1. **调整QPS限制**: 根据网络情况调整API调用频率
2. **合理设置批处理大小**: 平衡内存使用和处理效率
3. **定期清理日志**: 避免日志文件过大影响性能
4. **监控系统资源**: 确保有足够的内存和CPU资源

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交Issue和Pull Request！请查看 [贡献指南](CONTRIBUTING.md) 了解详情。

### 贡献方式

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📞 联系方式

- **作者**: jonntd@gmail.com
- **项目地址**: https://github.com/jonntd/pan115-scraper
- **问题反馈**: https://github.com/jonntd/pan115-scraper/issues
- **讨论交流**: https://github.com/jonntd/pan115-scraper/discussions

## 🙏 致谢

感谢以下开源项目和服务：

- [Flask](https://flask.palletsprojects.com/) - Web框架
- [TMDB](https://www.themoviedb.org/) - 电影数据库
- [Gemini AI](https://ai.google.dev/) - AI服务
- [115云盘](https://115.com/) - 云存储服务

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个Star支持一下！**

**📢 欢迎分享给更多需要的朋友！**

</div>