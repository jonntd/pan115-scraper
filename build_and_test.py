#!/usr/bin/env python3
"""
完整的构建和测试流程脚本
自动化PyInstaller打包和测试过程
"""

import os
import sys
import subprocess
import time
import shutil
import platform
from pathlib import Path

class BuildTester:
    def __init__(self):
        self.platform = platform.system().lower()
        self.exe_name = self.get_exe_name()
        self.build_dir = Path("build")
        self.dist_dir = Path("dist")
        
    def get_exe_name(self):
        """获取平台对应的可执行文件名"""
        if self.platform == "windows":
            return "pan115-scraper-win.exe"
        elif self.platform == "darwin":
            return "pan115-scraper-mac"
        else:
            return "pan115-scraper-linux"
    
    def print_step(self, step, message):
        """打印步骤信息"""
        print(f"\n{'='*60}")
        print(f"步骤 {step}: {message}")
        print('='*60)
    
    def run_command(self, command, description, timeout=300):
        """运行命令并处理输出"""
        print(f"🔧 {description}...")
        print(f"命令: {' '.join(command) if isinstance(command, list) else command}")
        
        try:
            if isinstance(command, str):
                command = command.split()
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                print(f"✅ {description} 成功")
                if result.stdout.strip():
                    print("输出:", result.stdout.strip())
                return True
            else:
                print(f"❌ {description} 失败")
                print("错误输出:", result.stderr.strip())
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {description} 超时")
            return False
        except Exception as e:
            print(f"❌ {description} 异常: {e}")
            return False
    
    def check_prerequisites(self):
        """检查构建前提条件"""
        self.print_step(1, "检查构建前提条件")
        
        # 检查Python版本
        python_version = sys.version_info
        print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        if python_version < (3, 8):
            print("❌ Python版本过低，需要3.8+")
            return False
        
        # 检查必要文件
        required_files = [
            "app.py",
            "requirements.txt",
            "pan115-scraper.spec",
            "templates/index.html",
            "static/style.css",
            "static/script.js"
        ]
        
        for file_path in required_files:
            if not Path(file_path).exists():
                print(f"❌ 缺少必要文件: {file_path}")
                return False
            print(f"✅ 找到文件: {file_path}")
        
        return True
    
    def install_dependencies(self):
        """安装依赖"""
        self.print_step(2, "安装依赖")
        
        # 升级pip
        if not self.run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], "升级pip"):
            return False
        
        # 安装PyInstaller
        if not self.run_command([sys.executable, "-m", "pip", "install", "pyinstaller"], "安装PyInstaller"):
            return False
        
        # 安装项目依赖
        if not self.run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], "安装项目依赖"):
            return False
        
        return True
    
    def clean_build(self):
        """清理构建目录"""
        self.print_step(3, "清理构建目录")
        
        dirs_to_clean = [self.build_dir, self.dist_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"🧹 已清理: {dir_path}")
        
        # 清理spec备份文件
        for spec_backup in Path(".").glob("*.spec.bak"):
            spec_backup.unlink()
            print(f"🧹 已清理: {spec_backup}")
        
        return True
    
    def build_executable(self):
        """构建可执行文件"""
        self.print_step(4, "构建可执行文件")
        
        return self.run_command(
            [sys.executable, "-m", "PyInstaller", "pan115-scraper.spec"],
            "PyInstaller构建",
            timeout=600  # 10分钟超时
        )
    
    def verify_build(self):
        """验证构建结果"""
        self.print_step(5, "验证构建结果")
        
        exe_path = self.dist_dir / self.exe_name
        if not exe_path.exists():
            print(f"❌ 可执行文件不存在: {exe_path}")
            return False
        
        # 检查文件大小
        file_size = exe_path.stat().st_size / 1024 / 1024  # MB
        print(f"✅ 可执行文件存在: {exe_path}")
        print(f"📊 文件大小: {file_size:.1f} MB")
        
        # 检查是否可执行
        if not os.access(exe_path, os.X_OK):
            print("⚠️  文件没有执行权限，尝试添加...")
            try:
                exe_path.chmod(0o755)
                print("✅ 已添加执行权限")
            except Exception as e:
                print(f"❌ 添加执行权限失败: {e}")
                return False
        
        return True
    
    def test_executable(self):
        """测试可执行文件"""
        self.print_step(6, "测试可执行文件")
        
        exe_path = self.dist_dir / self.exe_name
        
        print("🚀 启动应用程序进行测试...")
        try:
            # 启动应用程序
            process = subprocess.Popen(
                [str(exe_path)],
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
            
            # 测试HTTP连接
            try:
                import requests
                response = requests.get('http://127.0.0.1:5001', timeout=10)
                if response.status_code == 200:
                    print("✅ HTTP连接测试通过")
                    success = True
                else:
                    print(f"⚠️  HTTP连接异常，状态码: {response.status_code}")
                    success = False
            except Exception as e:
                print(f"⚠️  HTTP连接测试失败: {e}")
                success = False
            
            # 终止进程
            print("🛑 终止测试进程...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            return success
            
        except Exception as e:
            print(f"❌ 测试过程异常: {e}")
            return False
    
    def create_distribution(self):
        """创建发布包"""
        self.print_step(7, "创建发布包")
        
        # 复制必要文件到dist目录
        files_to_copy = [
            ("config.json.example", "config.json.example"),
            ("README.md", "README.md"),
            ("LICENSE", "LICENSE"),
            ("PYINSTALLER_GUIDE.md", "PYINSTALLER_GUIDE.md"),
        ]
        
        for src, dst in files_to_copy:
            src_path = Path(src)
            dst_path = self.dist_dir / dst
            
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
                print(f"📄 已复制: {src} -> {dst}")
            else:
                print(f"⚠️  文件不存在: {src}")
        
        print("✅ 发布包创建完成")
        return True
    
    def run_full_build(self):
        """运行完整构建流程"""
        print("🚀 Pan115 Scraper 自动构建和测试")
        print(f"平台: {self.platform}")
        print(f"目标可执行文件: {self.exe_name}")
        
        steps = [
            ("检查前提条件", self.check_prerequisites),
            ("安装依赖", self.install_dependencies),
            ("清理构建目录", self.clean_build),
            ("构建可执行文件", self.build_executable),
            ("验证构建结果", self.verify_build),
            ("测试可执行文件", self.test_executable),
            ("创建发布包", self.create_distribution),
        ]
        
        for step_name, step_func in steps:
            if not step_func():
                print(f"\n❌ 构建失败于步骤: {step_name}")
                return False
        
        print("\n🎉 构建和测试完成！")
        print(f"📁 可执行文件位置: {self.dist_dir / self.exe_name}")
        print("📋 使用说明:")
        print("1. 将dist目录中的文件复制到目标机器")
        print("2. 根据config.json.example创建config.json配置文件")
        print("3. 运行可执行文件")
        print("4. 访问 http://localhost:5001")
        
        return True

def main():
    """主函数"""
    builder = BuildTester()
    success = builder.run_full_build()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
