#!/bin/bash

# Pan115 Scraper 启动脚本

echo "🚀 启动 Pan115 Scraper..."

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "⚠️  未找到配置文件 config.json"
    if [ -f "config.json.example" ]; then
        echo "📋 发现示例配置文件，正在复制..."
        cp config.json.example config.json
        echo "✅ 已创建默认配置文件"
        echo "🔧 请编辑 config.json 文件，填入您的配置信息"
        echo ""
    else
        echo "❌ 未找到示例配置文件，请手动创建 config.json"
        exit 1
    fi
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📥 安装/更新依赖..."
pip install -r requirements.txt

# 检查端口占用
PORT=5001
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 $PORT 已被占用"
    echo "🔍 占用进程信息:"
    lsof -i :$PORT
    echo ""
    read -p "是否要终止占用进程并继续？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🛑 终止占用进程..."
        lsof -ti:$PORT | xargs kill -9
        sleep 2
    else
        echo "❌ 启动取消"
        exit 1
    fi
fi

# 启动应用
echo "🌟 启动 Pan115 Scraper..."
echo "📱 访问地址: http://localhost:$PORT"
echo "🛑 按 Ctrl+C 停止服务"
echo ""

python app.py
