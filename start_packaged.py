#!/usr/bin/env python3
"""
打包版本启动脚本
用于测试PyInstaller打包后的应用程序
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def find_executable():
    """查找可执行文件"""
    if sys.platform == "win32":
        exe_name = "pan115-scraper-win.exe"
    elif sys.platform == "darwin":
        exe_name = "pan115-scraper-mac"
    else:
        exe_name = "pan115-scraper-linux"
    
    # 可能的路径
    possible_paths = [
        f"dist/{exe_name}",
        exe_name,
        f"./{exe_name}",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def check_config():
    """检查配置文件"""
    config_paths = [
        "config.json",
        "config.json.example",
        "dist/config.json",
        "dist/config.json.example",
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            return path
    
    return None

def create_default_config():
    """创建默认配置文件"""
    default_config = {
        "QPS_LIMIT": 3,
        "CHUNK_SIZE": 50,
        "MAX_WORKERS": 4,
        "COOKIES": "",
        "TMDB_API_KEY": "",
        "GEMINI_API_KEY": "",
        "GEMINI_API_URL": "",
        "MODEL": "gemini-2.5-flash-lite-preview-06-17-search",
        "LANGUAGE": "zh-CN",
        "KILL_OCCUPIED_PORT_PROCESS": True
    }
    
    import json
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        print("✅ 已创建默认配置文件: config.json")
        return True
    except Exception as e:
        print(f"❌ 创建配置文件失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 Pan115 Scraper 启动器")
    print("=" * 40)
    
    # 查找可执行文件
    exe_path = find_executable()
    if not exe_path:
        print("❌ 未找到可执行文件")
        print("请确保已经运行构建脚本生成可执行文件")
        return False
    
    print(f"✅ 找到可执行文件: {exe_path}")
    
    # 检查配置文件
    config_path = check_config()
    if not config_path:
        print("⚠️  未找到配置文件，创建默认配置...")
        if not create_default_config():
            return False
    else:
        print(f"✅ 找到配置文件: {config_path}")
    
    # 启动应用程序
    print("🚀 启动应用程序...")
    try:
        # 启动应用
        process = subprocess.Popen([exe_path])
        
        # 等待应用启动
        print("⏳ 等待应用启动...")
        time.sleep(5)
        
        # 检查进程是否还在运行
        if process.poll() is not None:
            print("❌ 应用程序启动失败")
            return False
        
        print("✅ 应用程序启动成功")
        print("📱 访问地址: http://localhost:5001")
        
        # 询问是否打开浏览器
        try:
            response = input("是否打开浏览器？(y/N): ").strip().lower()
            if response in ['y', 'yes']:
                webbrowser.open('http://localhost:5001')
                print("🌐 已打开浏览器")
        except KeyboardInterrupt:
            pass
        
        print("\n🛑 按 Ctrl+C 停止应用程序")
        
        # 等待用户中断
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n🛑 正在停止应用程序...")
            process.terminate()
            try:
                process.wait(timeout=5)
                print("✅ 应用程序已停止")
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                print("🔪 强制终止应用程序")
        
        return True
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        input("按回车键退出...")
    sys.exit(0 if success else 1)
