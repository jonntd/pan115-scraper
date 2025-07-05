#!/usr/bin/env python3
"""
测试打包后的网页显示问题
"""

import os
import sys
import subprocess
import time
import requests
import webbrowser
from pathlib import Path

def test_web_display():
    """测试网页显示"""
    print("🧪 测试打包后的网页显示")
    print("=" * 50)
    
    # 查找可执行文件
    exe_path = "./dist/pan115-scraper-mac"
    if not os.path.exists(exe_path):
        print(f"❌ 可执行文件不存在: {exe_path}")
        return False
    
    print(f"✅ 找到可执行文件: {exe_path}")
    
    # 启动应用程序
    port = 5004
    print(f"🚀 启动应用程序在端口 {port}...")
    
    try:
        process = subprocess.Popen(
            [exe_path, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待启动
        print("⏳ 等待应用启动...")
        time.sleep(8)
        
        # 检查进程状态
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print("❌ 应用程序启动失败")
            print("标准输出:", stdout)
            print("错误输出:", stderr)
            return False
        
        print("✅ 应用程序启动成功")
        
        # 测试各种端点
        base_url = f"http://127.0.0.1:{port}"
        
        tests = [
            ("主页", "/"),
            ("健康检查", "/api/health"),
            ("CSS文件", "/static/style.css"),
            ("JS文件", "/static/script.js"),
        ]
        
        all_passed = True
        
        for test_name, endpoint in tests:
            try:
                url = base_url + endpoint
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ {test_name}: {response.status_code}")
                    
                    # 对于主页，检查内容
                    if endpoint == "/":
                        content = response.text
                        if "115云盘刮削工具" in content:
                            print("  ✅ 页面标题正确")
                        else:
                            print("  ❌ 页面标题不正确")
                            all_passed = False
                        
                        if "/static/style.css" in content:
                            print("  ✅ CSS引用正确")
                        else:
                            print("  ❌ CSS引用不正确")
                            all_passed = False
                        
                        if "/static/script.js" in content:
                            print("  ✅ JS引用正确")
                        else:
                            print("  ❌ JS引用不正确")
                            all_passed = False
                    
                    # 对于静态文件，检查内容长度
                    elif endpoint.startswith("/static/"):
                        if len(response.text) > 100:
                            print(f"  ✅ 文件内容正常 ({len(response.text)} 字符)")
                        else:
                            print(f"  ❌ 文件内容可能有问题 ({len(response.text)} 字符)")
                            all_passed = False
                
                else:
                    print(f"❌ {test_name}: {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ {test_name}: 异常 - {e}")
                all_passed = False
        
        # 如果所有测试通过，打开浏览器
        if all_passed:
            print("\n🎉 所有测试通过！")
            print(f"🌐 访问地址: {base_url}")
            
            try:
                response = input("是否打开浏览器查看页面？(y/N): ").strip().lower()
                if response in ['y', 'yes']:
                    webbrowser.open(base_url)
                    print("🌐 已打开浏览器")
                    
                    # 等待用户确认
                    input("请在浏览器中查看页面，然后按回车键继续...")
            except KeyboardInterrupt:
                pass
        else:
            print("\n❌ 部分测试失败")
        
        # 终止进程
        print("\n🛑 终止应用程序...")
        process.terminate()
        try:
            process.wait(timeout=5)
            print("✅ 应用程序已停止")
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            print("🔪 强制终止应用程序")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ 测试过程异常: {e}")
        return False

def main():
    """主函数"""
    success = test_web_display()
    
    if success:
        print("\n🎉 网页显示测试通过！")
        print("如果浏览器中页面显示正常，说明打包没有问题。")
        print("如果页面显示异常，可能是以下原因：")
        print("1. 浏览器缓存问题 - 尝试强制刷新 (Ctrl+F5)")
        print("2. 浏览器控制台有JavaScript错误")
        print("3. 网络连接问题")
    else:
        print("\n❌ 网页显示测试失败！")
        print("请检查应用程序日志和错误信息。")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
