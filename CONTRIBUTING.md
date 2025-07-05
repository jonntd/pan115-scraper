# 贡献指南

感谢您对 Pan115 Scraper 项目的关注和贡献！

## 🤝 如何贡献

### 报告问题

如果您发现了bug或有功能建议，请：

1. 检查 [Issues](https://github.com/yourusername/pan115-scraper/issues) 中是否已有相关问题
2. 如果没有，请创建新的Issue，包含：
   - 详细的问题描述
   - 复现步骤
   - 期望的行为
   - 实际的行为
   - 系统环境信息

### 提交代码

1. **Fork 项目**
   ```bash
   git clone https://github.com/yourusername/pan115-scraper.git
   cd pan115-scraper
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **开发和测试**
   - 遵循现有的代码风格
   - 添加必要的测试
   - 确保所有测试通过

4. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **创建 Pull Request**
   - 提供清晰的PR描述
   - 关联相关的Issue
   - 等待代码审查

## 📝 代码规范

### Python代码风格

- 遵循 PEP 8 规范
- 使用有意义的变量和函数名
- 添加适当的注释和文档字符串
- 保持函数简洁，单一职责

### 提交信息规范

使用约定式提交格式：

- `feat:` 新功能
- `fix:` 修复bug
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建过程或辅助工具的变动

## 🧪 测试

在提交代码前，请确保：

1. 代码能够正常运行
2. 新功能有相应的测试
3. 所有现有测试仍然通过

## 📋 开发环境设置

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境**
   - 复制 `config.json.example` 到 `config.json`
   - 填入必要的配置信息

3. **运行应用**
   ```bash
   python app.py
   ```

## 🎯 优先级功能

当前需要帮助的功能：

1. **多语言支持** - 添加更多语言界面
2. **云盘支持** - 支持其他云盘服务
3. **性能优化** - 提升大文件处理性能
4. **用户体验** - 改进界面和交互
5. **文档完善** - 补充使用文档和示例

## 💡 功能建议

欢迎提出新的功能建议，特别是：

- 新的AI模型集成
- 更多的媒体信息源
- 自动化工具和脚本
- 移动端支持
- 插件系统

## 📞 联系方式

如有任何问题，可以通过以下方式联系：

- 创建 GitHub Issue
- 发送邮件到 jonntd@gmail.com
- 在 GitHub Discussions 中讨论

感谢您的贡献！🎉
