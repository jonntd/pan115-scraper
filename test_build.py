#!/usr/bin/env python3
"""
PyInstaller打包测试脚本
用于验证打包后的可执行文件是否正常工作
"""

import os
import sys
import subprocess
import time
import requests
import threading
from pathlib import Path

def test_executable(exe_path):
    """测试可执行文件"""
    print(f"🧪 测试可执行文件: {exe_path}")
    
    if not os.path.exists(exe_path):
        print(f"❌ 可执行文件不存在: {exe_path}")
        return False
    
    print(f"✅ 可执行文件存在，大小: {os.path.getsize(exe_path) / 1024 / 1024:.1f} MB")
    
    # 启动应用程序
    print("🚀 启动应用程序...")
    try:
        # 在后台启动应用
        process = subprocess.Popen(
            [exe_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待应用启动
        print("⏳ 等待应用启动...")
        time.sleep(10)
        
        # 检查进程是否还在运行
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ 应用程序启动失败")
            print(f"标准输出: {stdout}")
            print(f"错误输出: {stderr}")
            return False
        
        # 测试HTTP连接
        print("🌐 测试HTTP连接...")
        try:
            response = requests.get('http://127.0.0.1:5001', timeout=5)
            if response.status_code == 200:
                print("✅ HTTP连接成功")
                success = True
            else:
                print(f"❌ HTTP连接失败，状态码: {response.status_code}")
                success = False
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP连接异常: {e}")
            success = False
        
        # 测试API端点
        if success:
            print("🔌 测试API端点...")
            try:
                api_response = requests.get('http://127.0.0.1:5001/api/health', timeout=5)
                if api_response.status_code == 200:
                    print("✅ API端点正常")
                else:
                    print(f"⚠️  API端点响应异常，状态码: {api_response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️  API端点测试失败: {e}")
        
        # 终止进程
        print("🛑 终止应用程序...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    print("🚀 Pan115 Scraper 打包测试")
    print("=" * 50)
    
    # 检测平台并确定可执行文件名
    if sys.platform == "win32":
        exe_name = "pan115-scraper-win.exe"
    elif sys.platform == "darwin":
        exe_name = "pan115-scraper-mac"
    else:
        exe_name = "pan115-scraper-linux"
    
    # 查找可执行文件
    possible_paths = [
        f"dist/{exe_name}",
        exe_name,
        f"./{exe_name}",
    ]
    
    exe_path = None
    for path in possible_paths:
        if os.path.exists(path):
            exe_path = path
            break
    
    if not exe_path:
        print(f"❌ 未找到可执行文件: {exe_name}")
        print("可能的路径:")
        for path in possible_paths:
            print(f"  - {path}")
        return False
    
    # 检查配置文件
    config_paths = [
        "config.json",
        "config.json.example",
        f"{os.path.dirname(exe_path)}/config.json",
        f"{os.path.dirname(exe_path)}/config.json.example",
    ]
    
    config_found = False
    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"✅ 找到配置文件: {config_path}")
            config_found = True
            break
    
    if not config_found:
        print("⚠️  未找到配置文件，应用可能无法正常工作")
    
    # 运行测试
    success = test_executable(exe_path)
    
    print("=" * 50)
    if success:
        print("🎉 测试通过！应用程序打包成功")
        return True
    else:
        print("❌ 测试失败！请检查打包配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
