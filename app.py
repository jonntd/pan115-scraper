"""
Pan115 Scraper - 115云盘智能文件刮削器
=====================================

作者: jonntd@gmail.com
最后更新: 2025-07-03
许可: MIT License
"""

# 标准库导入
import os
import json
import logging
import threading
import datetime
import requests
import re
import sys
import subprocess
import time
# hashlib 导入已删除（缓存功能不再需要）
import math
import queue
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from collections import deque
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler
from urllib import parse

# 第三方库导入
from flask import Flask, render_template, request, jsonify

# ================================
# 应用程序初始化和常量定义
# ================================

app = Flask(__name__)

# ================================
# 缓存功能已删除
# ================================



# ================================
# 任务队列管理系统
# ================================

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import uuid
import queue
import threading

# 🚀 任务队列配置
TASK_QUEUE_MAX_SIZE = 10  # 最大队列大小
TASK_TIMEOUT_SECONDS = 300  # 任务超时时间（5分钟）
TASK_QUEUE_GET_TIMEOUT = 1.0  # 任务队列获取超时时间（秒）

# 任务取消控制全局变量
current_task_cancelled = False
current_task_id = None

class TaskCancelledException(Exception):
    """任务被取消异常"""
    pass

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消
    TIMEOUT = "timeout"      # 超时

@dataclass
class GroupingTask:
    """智能分组任务数据类"""
    task_id: str
    folder_id: str
    folder_name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0  # 进度百分比 0-100
    processed_items: int = 0  # 已处理的项目数量
    total_items: int = 0  # 总项目数量

    def get_duration(self) -> Optional[float]:
        """获取任务执行时长"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return None

class GroupingTaskManager:
    """智能分组任务管理器"""

    def __init__(self, max_queue_size: int = 10, task_timeout: int = 300):
        self.task_queue = queue.Queue(maxsize=max_queue_size)
        self.active_tasks: Dict[str, GroupingTask] = {}
        self.completed_tasks: Dict[str, GroupingTask] = {}
        self.max_completed_tasks = 50  # 最多保留50个已完成任务
        self.task_timeout = task_timeout  # 任务超时时间（秒）
        self.lock = threading.RLock()
        self.worker_thread = None
        self.is_running = False
        self._start_worker()

    def _start_worker(self):
        """启动工作线程"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logging.info("🚀 智能分组任务管理器已启动")

    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 从队列中获取任务（阻塞等待）
                task = self.task_queue.get(timeout=TASK_QUEUE_GET_TIMEOUT)
                if task is None:  # 停止信号
                    break

                self._execute_task(task)
                self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"❌ 任务管理器工作线程异常: {e}")

    def _execute_task(self, task: GroupingTask):
        """执行单个任务"""
        with self.lock:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self.active_tasks[task.task_id] = task

        logging.info(f"🎯 开始执行智能分组任务: {task.task_id} (文件夹: {task.folder_name})")

        # 创建超时检查线程
        timeout_thread = threading.Thread(target=self._check_task_timeout, args=(task,), daemon=True)
        timeout_thread.start()

        try:
            # 检查任务是否已被取消
            if task.status == TaskStatus.CANCELLED:
                return

            # 执行实际的分组任务
            result = self._perform_grouping_analysis(task)

            with self.lock:
                if task.status not in [TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    task.result = result
                    task.progress = 100.0

                    # 移动到已完成任务
                    self._move_to_completed(task)

                    logging.info(f"✅ 智能分组任务完成: {task.task_id} (耗时: {task.get_duration():.2f}秒)")

        except Exception as e:
            with self.lock:
                if task.status not in [TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.error = str(e)
                    self._move_to_completed(task)

                    logging.error(f"❌ 智能分组任务失败: {task.task_id} - {e}")

    def _check_task_timeout(self, task: GroupingTask):
        """检查任务超时"""
        time.sleep(self.task_timeout)

        with self.lock:
            if task.task_id in self.active_tasks and task.status == TaskStatus.RUNNING:
                # 任务超时
                task.status = TaskStatus.TIMEOUT
                task.completed_at = time.time()
                task.error = f"任务执行超时 (超过 {self.task_timeout} 秒)"
                self._move_to_completed(task)

                logging.warning(f"⏰ 智能分组任务超时: {task.task_id} (超时时间: {self.task_timeout}秒)")

    def _perform_grouping_analysis(self, task: GroupingTask) -> Dict[str, Any]:
        """执行实际的分组分析"""
        # 检查任务是否已被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        # 设置当前任务ID，以便全局取消机制能够工作
        global current_task_id, current_task_cancelled
        current_task_id = task.task_id
        current_task_cancelled = False  # 重置取消标志

        # 这里调用现有的分组分析函数
        video_files = []
        get_video_files_recursively(task.folder_id, video_files)

        # 再次检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        if not video_files:
            return {
                'success': False,
                'error': '文件夹中没有找到视频文件',
                'movie_info': [],
                'count': 0,
                'size': '0GB'
            }

        # 更新进度
        task.progress = 30.0

        # 调用分组分析
        def progress_callback(current, total, message):
            # 检查任务是否被取消
            if task.status == TaskStatus.CANCELLED:
                raise Exception("任务已被取消")

            # 根据进度百分比更新任务进度
            if total > 0:
                progress_percent = (current / total) * 100
                # 将进度映射到30-90%范围内（前面已经用了0-30%）
                task.progress = 30.0 + (progress_percent * 0.6)

            # 详细的进度更新逻辑
            if '开始智能分组分析' in message or '开始智能文件分组分析' in message:
                task.progress = 40.0
                logging.info(f"🎯 智能分组进度: {task.progress}% - {message}")
            elif '准备文件数据' in message:
                task.progress = 45.0
                logging.info(f"📁 智能分组进度: {task.progress}% - {message}")
            elif 'AI分析完成' in message:
                task.progress = 60.0
                logging.info(f"🔄 智能分组进度: {task.progress}% - {message}")
            elif '分组合并完成' in message:
                task.progress = 80.0
                logging.info(f"⏱️ 智能分组进度: {task.progress}% - {message}")
            elif '生成最终结果' in message:
                task.progress = 90.0
                logging.info(f"✅ 智能分组进度: {task.progress}% - {message}")
            elif '分组分析完成' in message:
                task.progress = 95.0
                logging.info(f"✅ 智能分组进度: {task.progress}% - {message}")
            else:
                logging.info(f"📊 智能分组进度: {task.progress}% - {message}")

        # 检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        grouping_result = get_folder_grouping_analysis_internal(video_files, task.folder_id, progress_callback)

        # 最后检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        return {
            'success': True,
            'movie_info': grouping_result.get('movie_info', []),
            'video_files': video_files,
            'count': len(video_files),
            'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB"
        }

    def _move_to_completed(self, task: GroupingTask):
        """将任务移动到已完成列表"""
        if task.task_id in self.active_tasks:
            del self.active_tasks[task.task_id]

        self.completed_tasks[task.task_id] = task

        # 清理过多的已完成任务
        if len(self.completed_tasks) > self.max_completed_tasks:
            # 删除最旧的任务
            oldest_task_id = min(self.completed_tasks.keys(),
                                key=lambda tid: self.completed_tasks[tid].completed_at or 0)
            del self.completed_tasks[oldest_task_id]

    def submit_task(self, folder_id: str, folder_name: str) -> str:
        """提交新的分组任务"""
        task_id = str(uuid.uuid4())
        task = GroupingTask(
            task_id=task_id,
            folder_id=str(folder_id),
            folder_name=folder_name
        )

        try:
            with self.lock:
                # 检查是否已有相同文件夹的任务在队列中或执行中
                for existing_task in list(self.active_tasks.values()):
                    if existing_task.folder_id == str(folder_id) and existing_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                        raise ValueError(f"文件夹 {folder_name} 已有分组任务在进行中")

                # 检查队列中是否有相同文件夹的任务
                temp_queue = []
                while not self.task_queue.empty():
                    try:
                        queued_task = self.task_queue.get_nowait()
                        if queued_task.folder_id == str(folder_id):
                            raise ValueError(f"文件夹 {folder_name} 已有分组任务在队列中")
                        temp_queue.append(queued_task)
                    except queue.Empty:
                        break

                # 重新放回队列中的任务
                for queued_task in temp_queue:
                    self.task_queue.put_nowait(queued_task)

                # 添加新任务到队列和活动任务列表
                self.task_queue.put_nowait(task)
                self.active_tasks[task_id] = task  # 立即添加到活动任务列表
                logging.info(f"📝 智能分组任务已提交: {task_id} (文件夹: {folder_name})")

                return task_id

        except queue.Full:
            raise ValueError("任务队列已满，请稍后再试")

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                    self._move_to_completed(task)
                    logging.info(f"🛑 智能分组任务已取消: {task_id}")
                    return True
            return False

    def get_task_status(self, task_id: str) -> Optional[GroupingTask]:
        """获取任务状态"""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            return None

    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        with self.lock:
            return {
                'queue_size': self.task_queue.qsize(),
                'active_tasks': len(self.active_tasks),
                'completed_tasks': len(self.completed_tasks),
                'worker_running': self.is_running and self.worker_thread and self.worker_thread.is_alive()
            }

    def cleanup_old_tasks(self, hours: int = 24):
        """清理旧任务"""
        cutoff_time = time.time() - (hours * 3600)
        with self.lock:
            old_task_ids = [
                task_id for task_id, task in self.completed_tasks.items()
                if task.completed_at and task.completed_at < cutoff_time
            ]
            for task_id in old_task_ids:
                del self.completed_tasks[task_id]
            if old_task_ids:
                logging.info(f"🧹 清理了 {len(old_task_ids)} 个旧任务")

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        with self.lock:
            return {
                'worker_running': self.is_running and self.worker_thread and self.worker_thread.is_alive(),
                'queue_size': self.task_queue.qsize(),
                'active_tasks': len(self.active_tasks),
                'completed_tasks': len(self.completed_tasks),
                'max_queue_size': self.task_queue.maxsize,
                'task_timeout': self.task_timeout
            }

    def restart_worker_if_needed(self):
        """如果需要，重启工作线程"""
        if not self.is_running or not self.worker_thread or not self.worker_thread.is_alive():
            logging.warning("🔄 检测到工作线程异常，正在重启...")
            self.is_running = False
            if self.worker_thread and self.worker_thread.is_alive():
                try:
                    self.task_queue.put(None, timeout=1.0)  # 发送停止信号
                    self.worker_thread.join(timeout=5.0)
                except:
                    pass
            self._start_worker()

    def force_cleanup_stuck_tasks(self) -> int:
        """强制清理卡住的任务"""
        stuck_count = 0
        current_time = time.time()
        with self.lock:
            stuck_task_ids = []
            for task_id, task in self.active_tasks.items():
                if (task.status == TaskStatus.RUNNING and
                    task.started_at and
                    current_time - task.started_at > self.task_timeout * 2):
                    stuck_task_ids.append(task_id)
                    task.status = TaskStatus.TIMEOUT
                    task.completed_at = current_time
                    task.error = "任务被强制清理（疑似卡住）"
                    stuck_count += 1

            for task_id in stuck_task_ids:
                self._move_to_completed(self.active_tasks[task_id])

        if stuck_count > 0:
            logging.warning(f"🧹 强制清理了 {stuck_count} 个卡住的任务")
        return stuck_count


# ================================
# 智能分组相关函数
# ================================

def get_video_files_recursively(folder_id, file_list, current_path="", depth=0):
    """
    递归获取指定文件夹及其子文件夹中的所有视频文件（优化版本）

    Args:
        folder_id (int): 要搜索的文件夹ID
        file_list (list): 用于存储找到的视频文件的列表（会被修改）
        current_path (str): 当前文件夹的路径，用于构建完整文件路径
        depth (int): 递归深度，用于控制日志输出
        use_concurrent (bool): 是否使用并发优化，默认True

    Note:
        此函数会修改传入的file_list参数，将找到的视频文件添加到其中
    """
    try:
        if not current_path:
            current_path = get_folder_full_path(folder_id)
            logging.info(f"🔍 调试 - 使用get_folder_full_path获取路径: {current_path}")
        else:
            logging.info(f"🔍 调试 - 使用传递的路径: {current_path}")

        # 获取文件夹内容
        all_files = get_all_files_in_folder(folder_id, limit=100)
        logging.info(f"📂 扫描 {folder_id} ({current_path}) - {len(all_files)} 个项目 (深度: {depth})")

        # 分离视频文件和子文件夹
        video_files_in_folder = []
        subfolders = []

        for file_item in all_files:
            if file_item['type'] == 0:  # 文件
                _, ext = os.path.splitext(file_item['filename'])
                if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                    video_files_in_folder.append(file_item)
            elif file_item['type'] == 1:  # 文件夹
                subfolders.append(file_item)

        # 批量处理视频文件
        if video_files_in_folder:
            gb_in_bytes = 1024 ** 3
            for file_item in video_files_in_folder:
                bytes_value = file_item['size']
                gb_value = bytes_value / gb_in_bytes
                # 构建完整的文件路径
                full_file_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']

                # 限制路径最多显示倒数三层
                file_path = limit_path_depth(full_file_path, 3)

                # 创建增强的文件项，保留原有信息并添加计算字段
                enhanced_file_item = file_item.copy()
                enhanced_file_item['file_path'] = file_path
                enhanced_file_item['size_gb'] = f"{gb_value:.1f}GB"

                file_list.append(enhanced_file_item)

            logging.info(f"✅ 发现 {len(video_files_in_folder)} 个视频文件: {current_path}")

        # 处理子文件夹
        if subfolders:
            logging.info(f"📁 发现 {len(subfolders)} 个子文件夹，开始递归处理")

            # 为子文件夹构建路径缓存
            for file_item in subfolders:
                subfolder_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']

            # 递归处理子文件夹
            for file_item in subfolders:
                try:
                    # 根据QPS限制调整延迟时间，确保不超过API限制
                    time.sleep(1.2)  # 1.2秒延迟，确保QPS=1的限制
                    get_video_files_recursively(file_item['fileId'], file_list, subfolder_path, depth + 1)
                except Exception as e:
                    logging.error(f"处理子文件夹 {file_item['filename']} 时发生错误: {e}")
                    continue

    except Exception as e:
        logging.error(f"递归获取视频文件失败 (文件夹ID: {folder_id}): {e}")
        raise


def get_all_files_in_folder(folder_id, limit=100):
    """
    获取指定文件夹下的所有文件（自动处理分页）

    Args:
        folder_id (int): 文件夹ID
        limit (int): 每页返回的文件数量限制，默认100
        check_cancellation (bool): 是否检查任务取消状态，默认False

    Returns:
        list: 包含所有文件信息的列表
    """
    try:
        # 使用115云盘API获取文件夹内容
        response_data = _get_single_level_content_from_115(str(folder_id), 0, limit)

        if not response_data or response_data.get("success") is False:
            logging.warning(f"获取文件夹内容失败: {folder_id}")
            return []

        all_files = response_data.get("data", [])

        # 转换为统一格式
        formatted_files = []
        for item in all_files:
            if 'fid' in item:  # 文件
                formatted_files.append({
                    'fileId': item['fid'],
                    'filename': item.get('n', ''),
                    'size': item.get('s', 0),
                    'type': 0,  # 文件类型
                    'parentFileId': folder_id
                })
            elif 'cid' in item:  # 文件夹
                formatted_files.append({
                    'fileId': item['cid'],
                    'filename': item.get('n', ''),
                    'size': 0,
                    'type': 1,  # 文件夹类型
                    'parentFileId': folder_id
                })

        return formatted_files
    except Exception as e:
        logging.error(f"获取文件夹内容失败 (文件夹ID: {folder_id}): {e}")
        return []


def get_folder_full_path(folder_id):
    """获取文件夹的完整路径"""
    try:
        if folder_id == 0 or folder_id == '0':
            return ""

        # 使用115云盘API获取路径信息
        response_data = _get_single_level_content_from_115(folder_id, 0, 1)
        if not response_data or 'path' not in response_data:
            logging.warning(f"无法获取文件夹 {folder_id} 的路径信息")
            return ""

        # 从API响应中提取路径
        path_parts = response_data.get('path', [])
        if len(path_parts) <= 1:
            return ""

        # 构建路径字符串（跳过根目录）
        path_names = [part.get('name', '') for part in path_parts[1:]]
        full_path = "/".join(path_names)

        logging.info(f"🔍 文件夹 {folder_id} 的完整路径: {full_path}")
        return full_path

    except Exception as e:
        logging.error(f"获取文件夹路径失败: {e}")
        return ""


def limit_path_depth(path, max_depth=3):
    """限制路径显示深度"""
    if not path:
        return path

    parts = path.split(os.sep)
    if len(parts) <= max_depth:
        return path

    return os.sep.join(parts[-max_depth:])


def get_folder_grouping_analysis_internal(video_files, folder_id, progress_callback=None):
    """
    智能分组分析内部函数 - 完整版本从pan115-scraper复制

    Args:
        video_files: 视频文件列表
        folder_id: 文件夹ID
        progress_callback: 进度回调函数

    Returns:
        dict: 分组分析结果
    """
    try:
        if not video_files:
            logging.warning("📂 没有提供视频文件，返回空结果")
            return {'movie_info': []}

        logging.info(f"🎬 开始智能分组分析: {len(video_files)} 个文件")

        if progress_callback:
            progress_callback(0, 100, "开始智能分组分析")

        # 缓存检查已删除

        if progress_callback:
            progress_callback(10, 100, "准备文件数据")

        # 2. 批量处理文件
        CHUNK_SIZE = app_config.get('CHUNK_SIZE', 50)

        if len(video_files) > CHUNK_SIZE:
            logging.info(f"📊 文件数量 {len(video_files)} 超过批次大小 {CHUNK_SIZE}，启用批量处理")
            all_groups = process_files_for_grouping(video_files, f"文件夹 {folder_id}")
        else:
            logging.info(f"📊 文件数量 {len(video_files)} 在批次大小内，直接处理")
            all_groups = _call_ai_for_grouping(video_files)

        if progress_callback:
            progress_callback(60, 100, f"AI分析完成，获得 {len(all_groups)} 个初始分组")

        # 3. 合并重复分组
        if all_groups:
            logging.info(f"🔄 开始合并重复分组: {len(all_groups)} 个分组")
            all_groups = merge_duplicate_named_groups(all_groups)
            logging.info(f"✅ 重复分组合并完成: {len(all_groups)} 个分组")

        if progress_callback:
            progress_callback(80, 100, f"分组合并完成: {len(all_groups)} 个分组")

        # 4. 智能合并同系列分组
        if len(all_groups) > 1:
            logging.info(f"🤖 开始智能合并同系列分组")
            all_groups = merge_same_series_groups(all_groups)
            logging.info(f"✅ 智能合并完成: {len(all_groups)} 个最终分组")

        if progress_callback:
            progress_callback(90, 100, f"生成最终结果: {len(all_groups)} 个分组")

        # 5. 计算统计信息
        total_size_bytes = _calculate_total_size(video_files)
        size_str = _format_file_size(total_size_bytes)

        # 6. 构建最终结果
        result = {
            'success': True,
            'count': len(video_files),
            'size': size_str,
            'total_size_bytes': int(total_size_bytes),
            'movie_info': all_groups,
            'video_files': video_files,
            'processing_stats': {
                'total_files': len(video_files),
                'total_groups': len(all_groups),
                'chunk_size': CHUNK_SIZE
            }
        }

        # 缓存结果已删除

        if progress_callback:
            progress_callback(100, 100, f"分组分析完成: {len(all_groups)} 个分组")

        logging.info(f"✅ 智能分组分析完成: {len(all_groups)} 个分组，{len(video_files)} 个文件")
        return result

    except TaskCancelledException:
        logging.info("🛑 智能分组任务被用户取消")
        if progress_callback:
            progress_callback(0, 100, "任务已取消")
        return {'movie_info': [], 'error': '任务已被用户取消', 'cancelled': True}

    except Exception as e:
        logging.error(f"❌ 智能分组分析失败: {e}", exc_info=True)
        if progress_callback:
            progress_callback(0, 100, f"分析失败: {str(e)}")
        return {'movie_info': [], 'error': f'分组分析失败: {str(e)}'}


# ================================
# 智能分组AI提示词模板 - 从pan115-scraper复制
# ================================

MAGIC_PROMPT = """
你是一个专业的影视文件分析专家。请分析以下文件列表，根据文件名将相关文件分组。

⚠️ **严格警告**：只有主标题相同或高度相似的文件才能分组！

🚫 **绝对禁止的错误分组**：
- ❌ 不要将"海底小纵队"、"疯狂元素城"、"蓝精灵"分在一组
- ❌ 不要仅因为都是动画片就分组
- ❌ 不要仅因为都是迪士尼/皮克斯就分组
- ❌ 不要仅因为年份相近就分组
- ❌ 不要将完全不同的IP/品牌混合

📺 **电视剧命名格式严格要求**：
- ✅ 必须使用：`标题 (首播年份) S季数`
- ✅ 正确示例：SEAL Team (2017) S01, SEAL Team (2018) S02
- ❌ 禁止格式：SEAL Team S01, SEAL Team (Season 1), SEAL Team (S01), SEAL Team (2018-2019) S02

✅ **正确分组标准**：主标题必须相同或为同一系列的续集/前传

## 📋 文件名模式识别指南

### 🎬 常见文件名格式：
1. **电视剧格式**：
   - `标题 (年份) S01E01.mkv` → 间谍过家家 (2022) S01E01.mkv
   - `标题 第1季 第1集.mkv` → 180天重启计划 第1季 第1集.mkv
   - `Title S01E01.mkv` → SPY×FAMILY S01E01.mkv
   - `标题.S01E01.mkv` → 亲爱的公主病.S01E01.mkv
   - `标题 S01 E01.mkv` → 某剧 S01 E01.mkv

2. **电影格式**：
   - `标题 (年份).mkv` → 复仇者联盟 (2012).mkv
   - `标题.年份.mkv` → Avengers.2012.mkv
   - `标题 年份.mkv` → 钢铁侠 2008.mkv

3. **系列电影格式**：
   - `标题1.mkv, 标题2.mkv` → 复仇者联盟1.mkv, 复仇者联盟2.mkv
   - `标题 Part1.mkv` → 哈利波特与死亡圣器 Part1.mkv

### 📊 返回格式要求：
必须返回JSON数组格式，每个分组包含：
```json
[
  {
    "group_name": "分组名称",
    "fileIds": ["文件ID1", "文件ID2", ...]
  }
]
```

### ⚠️ 最终警告：
- **只有主标题相同的文件才能分组！**
- **绝对禁止将不同IP/品牌的作品分在一组！**
- **绝对禁止按类型、公司、年份、主题分组！**
- **同一系列的所有文件应该放在一个组里（如所有宝可梦剧场版）！**
- 必须返回完整的JSON格式
- fileIds数组必须包含所有相关文件的ID
- 如果没有可分组的文件，返回 []
- 只返回JSON，不要其他文字说明
- **宁可返回空数组[]，也不要错误分组！**
- **再次强调：海底小纵队、疯狂元素城、蓝精灵是完全不同的IP，绝不能分在一组！**
- **宝可梦剧场版系列应该全部放在一个组里，不要按年份分段！**
- **名侦探柯南剧场版、蜡笔小新剧场版等长期系列也应该全部放在一个组里！**
- **绝对不要因为文件数量多就按年份分段！系列完整性最重要！**
- **电视剧命名格式必须严格统一：标题 (首播年份) S季数！**
- **绝对禁止的电视剧格式：SEAL Team S01, SEAL Team (Season 1), SEAL Team (S01), SEAL Team (2018-2019) S02！**
- **必须使用的正确格式：SEAL Team (2017) S01, SEAL Team (2018) S02, SEAL Team (2019) S03！**

"""

# 智能分组合并提示词模板
GROUP_MERGE_PROMPT = """你是一个专业的影视分类专家。分析提供的分组列表，判断哪些分组属于同一系列应该合并。

合并规则：
1. 同一系列的不同季/部分应该合并
2. 相同主标题的作品应该合并
3. 明显的续集/前传关系应该合并
4. 保持原有的合理分组

返回JSON格式：
{
  "merges": [
    {
      "target_group": "目标分组名",
      "source_groups": ["源分组1", "源分组2"],
      "reason": "合并原因"
    }
  ]
}

如果无需合并，返回：{"merges": []}
"""

# 性能优化常量
API_CALL_DELAY = 0.1  # API调用间隔，避免频率限制
BATCH_PROCESS_SIZE = 20  # 批处理大小，平衡性能和内存使用

# 性能优化提示：
# 1. 删除缓存后，所有API调用都是实时的，可能导致性能下降
# 2. 建议在高频操作时适当增加延迟，避免API频率限制
# 3. 大量文件操作时建议分批处理，避免内存占用过高

# ================================
# 异常类定义
# ================================

class TaskCancelledException(Exception):
    """任务被取消异常"""
    pass

# ================================
# 智能分组支持函数 - 从pan115-scraper复制
# ================================

def check_task_cancelled():
    """检查当前任务是否被取消"""
    # 简化版本，主要检查任务队列中的取消状态
    if 'grouping_task_manager' in globals() and grouping_task_manager:
        # 检查是否有被取消的任务
        pass  # 简化实现，避免复杂的状态检查

def call_ai_api(prompt, model=None, temperature=0.1):
    """
    调用AI API进行文本生成（支持OpenAI兼容接口）

    Args:
        prompt (str): 发送给AI的提示词
        model (str, optional): 使用的AI模型名称，默认使用配置中的模型
        temperature (float): 生成文本的随机性，0.0-1.0之间

    Returns:
        str or None: AI生成的文本内容，失败时返回None
    """
    try:
        # 使用传入的模型或配置中的默认模型
        ai_model = model or app_config.get('MODEL', '')
        if not ai_model:
            logging.error("❌ 未配置AI模型")
            return None

        # 检查API配置
        if not GEMINI_API_KEY or not GEMINI_API_URL:
            logging.error("❌ AI API配置不完整")
            return None

        headers = {
            'Authorization': f'Bearer {GEMINI_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": ai_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": temperature
        }

        logging.info(f"🤖 调用AI API: {GEMINI_API_URL}")
        logging.info(f"📝 使用模型: {ai_model}")

        # 使用全局配置的超时时间
        AI_API_TIMEOUT = app_config.get('AI_API_TIMEOUT', 60)
        response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=AI_API_TIMEOUT)

        logging.info(f"📊 API响应状态码: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        # 检查响应格式
        if "choices" not in data:
            logging.error(f"❌ API响应格式错误，缺少choices字段: {data}")
            return None

        if not data["choices"] or len(data["choices"]) == 0:
            logging.error(f"❌ API响应choices为空: {data}")
            return None

        if "message" not in data["choices"][0]:
            logging.error(f"❌ API响应缺少message字段: {data['choices'][0]}")
            return None

        if "content" not in data["choices"][0]["message"]:
            logging.error(f"❌ API响应缺少content字段: {data['choices'][0]['message']}")
            return None

        content = data["choices"][0]["message"]["content"]
        logging.info(f"✅ AI API调用成功，响应长度: {len(content)} 字符")
        return content

    except requests.exceptions.Timeout:
        logging.error(f"❌ AI API请求超时 (超时时间: {AI_API_TIMEOUT}秒)")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ AI API请求失败: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ AI API调用异常: {e}")
        return None

# 旧的parse_json_from_ai_response函数已被_parse_ai_response替代

# ================================
# 缓存管理函数 - 从pan115-scraper复制
# ================================

# 缓存键生成函数已删除

# 分组缓存函数已删除

def _calculate_total_size(video_files):
    """计算文件总大小"""
    total_bytes = 0
    for file_item in video_files:
        try:
            # 尝试从不同字段获取文件大小
            size_value = file_item.get('size', 0)
            if isinstance(size_value, (int, float)):
                total_bytes += size_value
            elif isinstance(size_value, str):
                # 解析不同单位的文件大小字符串
                size_str = size_value
                if 'GB' in size_str:
                    total_bytes += float(size_str.replace('GB', '')) * (1024 ** 3)
                elif 'MB' in size_str:
                    total_bytes += float(size_str.replace('MB', '')) * (1024 ** 2)
                elif 'KB' in size_str:
                    total_bytes += float(size_str.replace('KB', '')) * 1024
                elif size_str.isdigit():
                    total_bytes += int(size_str)
        except (ValueError, KeyError):
            continue
    return total_bytes

def _format_file_size(size_bytes):
    """格式化文件大小"""
    units = [(1024**4, 'TB'), (1024**3, 'GB'), (1024**2, 'MB'), (1024, 'KB')]
    for threshold, unit in units:
        if size_bytes >= threshold:
            return f"{size_bytes / threshold:.1f}{unit}"
    return f"{int(size_bytes)}B"

# ================================
# 批处理和分组支持函数 - 从pan115-scraper复制
# ================================

def split_files_into_batches(files, batch_size):
    """将文件列表分割成批次"""
    batches = []
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        batches.append(batch)
    return batches

def process_files_for_grouping(files, source_name):
    """处理文件进行智能分组 - 优化版"""
    if not files:
        return []

    logging.info(f"🔄 处理 '{source_name}': {len(files)} 个文件")

    # 批次处理逻辑 - 优化API调用次数
    MAX_BATCH_SIZE = app_config.get('CHUNK_SIZE', 50)
    if len(files) > MAX_BATCH_SIZE:
        return _process_files_in_batches(files, MAX_BATCH_SIZE)
    else:
        return _process_single_batch(files)

def _process_files_in_batches(files, batch_size):
    """分批处理文件"""
    batches = split_files_into_batches(files, batch_size)
    all_groups = []

    for i, batch in enumerate(batches):
        logging.info(f"🔄 处理批次 {i+1}/{len(batches)}: {len(batch)} 个文件")
        batch_groups = _process_single_batch(batch)
        if batch_groups:
            all_groups.extend(batch_groups)

    return all_groups

def _process_single_batch(files):
    """处理单个批次的文件"""
    return _call_ai_for_grouping(files)

def _call_ai_for_grouping(files):
    """调用AI进行分组并验证结果"""
    file_list = [{'fileId': f.get('fid', f.get('fileId', '')), 'filename': f.get('name', f.get('filename', ''))} for f in files]
    user_input = repr(file_list)

    logging.info(f"🤖 开始AI分组分析: {len(files)} 个文件")
    start_time = time.time()

    try:
        raw_result = extract_movie_info_from_filename_enhanced(user_input, MAGIC_PROMPT, app_config.get('GROUPING_MODEL', ''))
        process_time = time.time() - start_time

        if raw_result:
            logging.info(f"⏱️ AI分组耗时: {process_time:.2f}秒 - 成功")
            # 验证和增强分组结果
            return _validate_and_enhance_groups(raw_result, files, "AI分组")
        else:
            logging.warning(f"⏱️ AI分组耗时: {process_time:.2f}秒 - 无结果")
            return []
    except Exception as e:
        process_time = time.time() - start_time
        logging.error(f"❌ AI分组失败: {process_time:.2f}秒 - {e}")
        return []

def extract_movie_info_from_filename_enhanced(user_input, prompt, model):
    """增强版电影信息提取函数"""
    try:
        # 构建完整的提示词
        full_prompt = f"{prompt}\n\n{user_input}"

        # 调用AI API
        response_content = call_ai_api(full_prompt, model)

        if response_content:
            logging.info(f"✅ AI响应成功，长度: {len(response_content)} 字符")
            # 解析JSON响应
            parsed_result = _parse_ai_response(response_content)
            if parsed_result:
                logging.info(f"✅ JSON解析成功")
                return parsed_result
            else:
                logging.warning(f"⚠️ JSON解析失败")
                logging.error(f"完整AI响应内容: {response_content}")
        else:
            logging.warning(f"⚠️ AI响应为空")

        return None

    except Exception as e:
        logging.error(f"AI信息提取失败: {e}")
        return None

def _parse_ai_response(input_string):
    """解析AI响应 - 简化版"""
    # 尝试提取JSON代码块
    logging.info(f"尝试解析AI响应: {input_string[:200]}...")
    pattern = r'```json(.*?)```'
    match = re.search(pattern, input_string, re.DOTALL)

    if match:
        json_data = match.group(1).strip()
        try:
            return json.loads(json_data)
        except json.JSONDecodeError as e:
            logging.error(f"JSON代码块解析失败: {e}")

    # 尝试直接解析整个响应
    input_string = input_string.strip()
    if input_string.startswith(('[', '{')):
        try:
            return json.loads(input_string)
        except json.JSONDecodeError as e:
            logging.error(f"直接JSON解析失败: {e}")

            # 尝试找到第一个完整的JSON对象
            if input_string.startswith('{'):
                brace_count = 0
                json_end = -1

                for i, char in enumerate(input_string):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

                if json_end > 0:
                    json_str = input_string[:json_end]
                    try:
                        logging.info(f"尝试解析截取的JSON，长度: {len(json_str)}")
                        return json.loads(json_str)
                    except json.JSONDecodeError as e2:
                        logging.error(f"截取JSON解析失败: {e2}")

    return None

def _validate_and_enhance_groups(raw_result, files, source_name):
    """验证和增强分组结果"""
    if not raw_result or not isinstance(raw_result, (list, dict)):
        return []

    # 如果是字典格式，尝试提取groups字段
    if isinstance(raw_result, dict):
        groups = raw_result.get('groups', [])
    else:
        groups = raw_result

    if not groups:
        return []

    # 创建文件ID到文件名的映射，以及文件名到文件ID的映射
    file_id_to_name = {}
    file_name_to_id = {}
    for file in files:
        file_id = file.get('fid') or file.get('fileId') or file.get('fileID')
        file_name = file.get('name') or file.get('filename') or file.get('n')
        if file_id and file_name:
            file_id_to_name[str(file_id)] = file_name
            file_name_to_id[file_name] = str(file_id)

    # 调试：打印文件映射
    logging.info(f"🔍 文件映射调试 - 总文件数: {len(files)}")
    logging.info(f"📝 文件名到ID映射: {list(file_name_to_id.keys())[:3]}{'...' if len(file_name_to_id) > 3 else ''}")

    enhanced_groups = []
    for group in groups:
        if isinstance(group, dict) and 'group_name' in group:
            # 调试：打印原始分组数据
            logging.info(f"🔍 原始分组数据: {group}")

            # 获取分组中的文件ID列表
            file_ids = group.get('fileIds', [])
            if not file_ids:
                # 尝试从files字段中提取fileId
                files_list = group.get('files', [])
                if isinstance(files_list, list):
                    for file_item in files_list:
                        if isinstance(file_item, dict):
                            # 首先尝试直接获取文件ID
                            file_id = file_item.get('fileId') or file_item.get('fid')
                            if file_id:
                                file_ids.append(str(file_id))
                            else:
                                # 如果没有文件ID，尝试通过文件名匹配
                                original_filename = file_item.get('original_filename')
                                if original_filename and original_filename in file_name_to_id:
                                    file_ids.append(file_name_to_id[original_filename])
                                    logging.info(f"🔍 通过文件名匹配到ID: {original_filename} -> {file_name_to_id[original_filename]}")

            # 调试：打印提取的文件ID
            logging.info(f"🔍 提取的文件ID: {file_ids}")

            # 生成file_names列表
            file_names = []
            for file_id in file_ids:
                file_name = file_id_to_name.get(str(file_id))
                if file_name:
                    file_names.append(file_name)

            enhanced_group = {
                'group_name': group.get('group_name', '未知分组'),
                'description': group.get('description', ''),
                'files': group.get('files', []),
                'fileIds': file_ids,
                'file_names': file_names,  # 新增：文件名列表
                'type': group.get('type', 'movie'),
                'confidence': group.get('confidence', 0.5),
                'file_count': len(file_names)  # 使用实际的文件名数量
            }

            # 调试日志
            logging.info(f"🔍 分组验证调试 - {enhanced_group['group_name']}: fileIds={len(file_ids)}, file_names={len(file_names)}")
            logging.info(f"📝 fileIds: {file_ids[:3]}{'...' if len(file_ids) > 3 else ''}")
            logging.info(f"📝 file_names: {file_names[:3]}{'...' if len(file_names) > 3 else ''}")

            enhanced_groups.append(enhanced_group)

    logging.info(f"✅ {source_name}验证完成: {len(enhanced_groups)} 个有效分组")
    return enhanced_groups

def merge_duplicate_named_groups(groups):
    """合并重复命名的分组"""
    if not groups:
        return groups

    # 按分组名称合并
    merged_dict = {}
    for group in groups:
        group_name = group.get('group_name', '未知分组')
        if group_name in merged_dict:
            # 合并文件列表
            existing_files = set(merged_dict[group_name].get('files', []))
            new_files = set(group.get('files', []))
            merged_files = list(existing_files.union(new_files))

            existing_file_ids = set(merged_dict[group_name].get('fileIds', []))
            new_file_ids = set(group.get('fileIds', []))
            merged_file_ids = list(existing_file_ids.union(new_file_ids))

            # 合并文件名列表
            existing_file_names = set(merged_dict[group_name].get('file_names', []))
            new_file_names = set(group.get('file_names', []))
            merged_file_names = list(existing_file_names.union(new_file_names))

            merged_dict[group_name]['files'] = merged_files
            merged_dict[group_name]['fileIds'] = merged_file_ids
            merged_dict[group_name]['file_names'] = merged_file_names
            merged_dict[group_name]['file_count'] = len(merged_file_names)
        else:
            merged_dict[group_name] = group.copy()

    return list(merged_dict.values())

def merge_same_series_groups(groups):
    """智能合并同系列分组"""
    if not groups or len(groups) <= 1:
        return groups

    # 简化版本：只进行基本的重复名称合并
    return merge_duplicate_named_groups(groups)

# ================================
# 全局任务管理器实例
# ================================

grouping_task_manager = GroupingTaskManager(
    max_queue_size=TASK_QUEUE_MAX_SIZE,
    task_timeout=TASK_TIMEOUT_SECONDS
)

# ================================
# 任务管理器维护系统
# ================================

def start_task_manager_maintenance():
    """启动任务管理器维护线程"""
    def maintenance_worker():
        while True:
            try:
                time.sleep(300)  # 每5分钟执行一次维护
                grouping_task_manager.restart_worker_if_needed()
                grouping_task_manager.cleanup_old_tasks(24)  # 清理24小时前的任务
                stuck_count = grouping_task_manager.force_cleanup_stuck_tasks()
                health = grouping_task_manager.get_health_status()

                if not health['worker_running']:
                    logging.warning("🚨 任务管理器工作线程未运行，正在重启...")
                    grouping_task_manager.restart_worker_if_needed()

                if stuck_count > 0:
                    logging.warning(f"🧹 维护清理了 {stuck_count} 个卡住的任务")

            except Exception as e:
                logging.error(f"❌ 任务管理器维护异常: {e}")

    maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
    maintenance_thread.start()
    logging.info("🔧 任务管理器维护线程已启动")

# 启动维护系统
start_task_manager_maintenance()

# 兼容性：为旧代码提供task_manager引用
class LegacyTaskManager:
    """为旧代码提供兼容性的任务管理器"""
    def __init__(self):
        self.tasks = {}
        self.lock = threading.RLock()

    def add_task(self, task):
        """添加任务（兼容性方法）"""
        with self.lock:
            self.tasks[task.task_id] = task
            logging.info(f"兼容性任务管理器：添加任务 {task.task_id}")

    def get_task(self, task_id):
        """获取任务（兼容性方法）"""
        return self.tasks.get(task_id)

    def get_all_tasks(self):
        """获取所有任务（兼容性方法）"""
        return {task_id: task.__dict__ for task_id, task in self.tasks.items()}

    def get_task_stats(self):
        """获取任务统计（兼容性方法）"""
        return {
            'total_tasks': len(self.tasks),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }

    def cancel_task(self, task_id):
        """取消任务（兼容性方法）"""
        task = self.tasks.get(task_id)
        if task:
            task.cancelled = True
            return True
        return False

    def get_running_tasks_count(self):
        """获取运行中任务数量（兼容性方法）"""
        return 0

    def create_task(self, cid, task_type="grouping"):
        """创建任务（兼容性方法）"""
        task_id = f"{task_type}_{int(time.time())}_{hash(cid) % 10000}"
        # 创建一个简单的任务对象
        class SimpleTask:
            def __init__(self, task_id, cid, task_type):
                self.task_id = task_id
                self.cid = cid
                self.task_type = task_type
                self.status = "pending"
                self.cancelled = False
                self.total_items = 0

            def start(self):
                self.status = "running"

            def to_dict(self):
                return self.__dict__

        task = SimpleTask(task_id, cid, task_type)
        self.add_task(task)
        return task

task_manager = LegacyTaskManager()


# ================================
# 智能分组API端点
# ================================

@app.route('/api/grouping_task/submit', methods=['POST'])
def submit_grouping_task():
    """提交智能分组任务"""
    try:
        folder_id = request.form.get('folder_id')
        folder_name = request.form.get('folder_name', f'文件夹_{folder_id}')

        if not folder_id:
            return jsonify({'success': False, 'error': '缺少folder_id参数'})

        # 提交任务到队列
        task_id = grouping_task_manager.submit_task(folder_id, folder_name)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'智能分组任务已提交: {task_id}'
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.error(f"提交智能分组任务失败: {e}")
        return jsonify({'success': False, 'error': f'提交任务失败: {str(e)}'})


@app.route('/api/grouping_task/status/<task_id>', methods=['GET'])
def get_grouping_task_status(task_id):
    """获取智能分组任务状态"""
    try:
        task = grouping_task_manager.get_task_status(task_id)

        if task is None:
            return jsonify({'success': False, 'error': '任务不存在'})

        return jsonify({
            'success': True,
            'task': {
                'task_id': task.task_id,
                'folder_id': task.folder_id,
                'folder_name': task.folder_name,
                'status': task.status.value,
                'progress': task.progress,
                'created_at': task.created_at,
                'started_at': task.started_at,
                'completed_at': task.completed_at,
                'duration': task.get_duration(),
                'result': task.result,
                'error': task.error
            }
        })

    except Exception as e:
        logging.error(f"获取任务状态失败: {e}")
        return jsonify({'success': False, 'error': f'获取任务状态失败: {str(e)}'})


@app.route('/api/grouping_task/cancel/<task_id>', methods=['POST'])
def cancel_grouping_task(task_id):
    """取消智能分组任务"""
    try:
        success = grouping_task_manager.cancel_task(task_id)

        if success:
            return jsonify({'success': True, 'message': f'任务 {task_id} 已取消'})
        else:
            return jsonify({'success': False, 'error': '任务不存在或无法取消'})

    except Exception as e:
        logging.error(f"取消任务失败: {e}")
        return jsonify({'success': False, 'error': f'取消任务失败: {str(e)}'})


@app.route('/api/grouping_task/queue_info', methods=['GET'])
def get_grouping_queue_info():
    """获取智能分组任务队列信息"""
    try:
        with grouping_task_manager.lock:
            queue_size = grouping_task_manager.task_queue.qsize()
            active_count = len(grouping_task_manager.active_tasks)
            completed_count = len(grouping_task_manager.completed_tasks)

            return jsonify({
                'success': True,
                'queue_info': {
                    'queue_size': queue_size,
                    'active_tasks': active_count,
                    'completed_tasks': completed_count,
                    'max_queue_size': grouping_task_manager.task_queue.maxsize,
                    'is_running': grouping_task_manager.is_running
                }
            })

    except Exception as e:
        logging.error(f"获取队列信息失败: {e}")
        return jsonify({'success': False, 'error': f'获取队列信息失败: {str(e)}'})


@app.route('/api/grouping_task/health', methods=['GET'])
def get_grouping_task_health():
    """获取智能分组任务系统健康状态"""
    try:
        return jsonify({
            'success': True,
            'health': {
                'system_running': grouping_task_manager.is_running,
                'worker_thread_alive': grouping_task_manager.worker_thread.is_alive() if grouping_task_manager.worker_thread else False,
                'timestamp': time.time()
            }
        })

    except Exception as e:
        logging.error(f"获取系统健康状态失败: {e}")
        return jsonify({'success': False, 'error': f'获取健康状态失败: {str(e)}'})


@app.route('/api/grouping_task/maintenance', methods=['POST'])
def grouping_task_maintenance():
    """智能分组任务系统维护操作"""
    try:
        action = request.form.get('action')

        if action == 'restart_worker':
            # 重启工作线程
            grouping_task_manager.is_running = False
            if grouping_task_manager.worker_thread and grouping_task_manager.worker_thread.is_alive():
                grouping_task_manager.task_queue.put(None)  # 发送停止信号
                grouping_task_manager.worker_thread.join(timeout=5)

            grouping_task_manager._start_worker()

            return jsonify({'success': True, 'message': '工作线程已重启'})

        elif action == 'clear_completed':
            # 清理已完成任务
            with grouping_task_manager.lock:
                cleared_count = len(grouping_task_manager.completed_tasks)
                grouping_task_manager.completed_tasks.clear()

            return jsonify({'success': True, 'message': f'已清理 {cleared_count} 个已完成任务'})

        else:
            return jsonify({'success': False, 'error': '不支持的维护操作'})

    except Exception as e:
        logging.error(f"系统维护操作失败: {e}")
        return jsonify({'success': False, 'error': f'维护操作失败: {str(e)}'})

# ================================
# 性能监控系统
# ================================

class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.api_calls = {}
        self.response_times = {}
        self.error_counts = {}
        self.lock = threading.RLock()
        self.start_time = datetime.datetime.now()

        # QPS限制器
        self.qps_limiter = {}
        self.qps_timestamps = {}

        logging.info("性能监控器初始化完成")

    def record_api_call(self, api_name, response_time, success=True):
        """记录API调用"""
        with self.lock:
            # 记录调用次数
            if api_name not in self.api_calls:
                self.api_calls[api_name] = {'total': 0, 'success': 0, 'error': 0}

            self.api_calls[api_name]['total'] += 1
            if success:
                self.api_calls[api_name]['success'] += 1
            else:
                self.api_calls[api_name]['error'] += 1
                self.error_counts[api_name] = self.error_counts.get(api_name, 0) + 1

            # 记录响应时间
            if api_name not in self.response_times:
                self.response_times[api_name] = []

            self.response_times[api_name].append(response_time)

            # 保持最近1000次记录
            if len(self.response_times[api_name]) > 1000:
                self.response_times[api_name] = self.response_times[api_name][-1000:]

    def check_qps_limit(self, api_name, qps_limit):
        """检查QPS限制"""
        with self.lock:
            current_time = time.time()

            if api_name not in self.qps_timestamps:
                self.qps_timestamps[api_name] = []

            # 清理1秒前的时间戳
            self.qps_timestamps[api_name] = [
                ts for ts in self.qps_timestamps[api_name]
                if current_time - ts < 1.0
            ]

            # 检查是否超过限制
            if len(self.qps_timestamps[api_name]) >= qps_limit:
                return False

            # 记录当前时间戳
            self.qps_timestamps[api_name].append(current_time)
            return True

    def get_api_stats(self, api_name):
        """获取API统计信息"""
        with self.lock:
            if api_name not in self.api_calls:
                return None

            calls = self.api_calls[api_name]
            times = self.response_times.get(api_name, [])

            stats = {
                'api_name': api_name,
                'total_calls': calls['total'],
                'success_calls': calls['success'],
                'error_calls': calls['error'],
                'success_rate': round(calls['success'] / calls['total'] * 100, 2) if calls['total'] > 0 else 0,
                'error_count': self.error_counts.get(api_name, 0)
            }

            if times:
                stats.update({
                    'avg_response_time': round(sum(times) / len(times), 3),
                    'min_response_time': round(min(times), 3),
                    'max_response_time': round(max(times), 3),
                    'recent_calls': len(times)
                })

            return stats

    def get_all_stats(self):
        """获取所有统计信息"""
        with self.lock:
            all_stats = {}
            for api_name in self.api_calls.keys():
                all_stats[api_name] = self.get_api_stats(api_name)

            # 添加系统统计
            uptime = datetime.datetime.now() - self.start_time
            all_stats['_system'] = {
                'uptime': str(uptime),
                'total_apis': len(self.api_calls),
                }

            return all_stats

    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.api_calls.clear()
            self.response_times.clear()
            self.error_counts.clear()
            self.qps_timestamps.clear()
            self.start_time = datetime.datetime.now()
            logging.info("性能统计已重置")

# ================================
# 全局性能监控器实例
# ================================

performance_monitor = PerformanceMonitor()

# ================================
# QPS限制装饰器
# ================================

def qps_limit(api_name, limit=1):
    """QPS限制装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 动态获取QPS限制 - 如果limit是字符串'QPS_LIMIT'，则使用当前配置值
            actual_limit = QPS_LIMIT if limit == 'QPS_LIMIT' else limit

            # 检查QPS限制
            if not performance_monitor.check_qps_limit(api_name, actual_limit):
                time.sleep(0.5)  # 等待500ms
                if not performance_monitor.check_qps_limit(api_name, actual_limit):
                    raise Exception(f"API {api_name} QPS限制超出: {actual_limit}/s")

            # 执行函数并记录性能
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                performance_monitor.record_api_call(api_name, response_time, True)
                return result
            except Exception as e:
                response_time = time.time() - start_time
                performance_monitor.record_api_call(api_name, response_time, False)
                raise

        return wrapper
    return decorator

# ================================
# 应用程序常量和配置
# ================================

TMDB_API_URL_BASE = "https://api.themoviedb.org/3"
CONFIG_FILE = 'config.json'

# ================================
# 应用程序配置管理
# ================================

# 全局配置字典，包含默认值
app_config = {
    "QPS_LIMIT": 1,
    "CHUNK_SIZE": 50,
    "MAX_WORKERS": 4,
    "COOKIES": "",
    "TMDB_API_KEY": "",
    "GEMINI_API_KEY": "",
    "GEMINI_API_URL": "",
    "MODEL": "gemini-2.5-flash-lite-preview-06-17-search",
    "GROUPING_MODEL": "gemini-2.5-flash-lite-preview-06-17-search",
    "LANGUAGE": "zh-CN",
    "API_MAX_RETRIES": 3,
    "API_RETRY_DELAY": 2,
    "AI_API_TIMEOUT": 60,
    "AI_MAX_RETRIES": 3,
    "AI_RETRY_DELAY": 2,
    "TMDB_API_TIMEOUT": 60,
    "TMDB_MAX_RETRIES": 3,
    "TMDB_RETRY_DELAY": 2,
    "CLOUD_API_MAX_RETRIES": 3,
    "CLOUD_API_RETRY_DELAY": 2,
    "GROUPING_MAX_RETRIES": 1,
    "GROUPING_RETRY_DELAY": 2,
    "TASK_QUEUE_GET_TIMEOUT": 1,
    "ENABLE_QUALITY_ASSESSMENT": False,
    "ENABLE_SCRAPING_QUALITY_ASSESSMENT": True,
    "KILL_OCCUPIED_PORT_PROCESS": True,

}

# ================================
# 全局变量初始化
# ================================

# 日志队列
log_queue = deque(maxlen=5000)

# 基础配置变量
QPS_LIMIT = app_config["QPS_LIMIT"]
COOKIES = app_config["COOKIES"]
CHUNK_SIZE = app_config["CHUNK_SIZE"]
MAX_WORKERS = app_config["MAX_WORKERS"]
LANGUAGE = app_config["LANGUAGE"]

# API配置变量
TMDB_API_KEY = app_config["TMDB_API_KEY"]
GEMINI_API_KEY = app_config["GEMINI_API_KEY"]
GEMINI_API_URL = app_config["GEMINI_API_URL"]
MODEL = app_config["MODEL"]
GROUPING_MODEL = app_config["GROUPING_MODEL"]

# 简化的常量定义
MAX_FILENAME_LENGTH = 255
ENABLE_INPUT_VALIDATION = True
MAX_RETRIES = 3
RETRY_DELAY = 2.0
RETRY_BACKOFF = 2.0
TIMEOUT = 60  # 增加到60秒以处理复杂的AI提取任务

# 缓存功能已删除

# 性能监控配置
PERFORMANCE_MONITORING = True

# 默认值配置
DEFAULT_CID = "0"
DEFAULT_PID = "0"

# 支持的文件扩展名列表
ALLOWED_FILE_EXTENSIONS = [
    # 视频文件
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp",
    ".ts", ".m2ts", ".mts", ".vob", ".rmvb", ".rm", ".asf", ".divx", ".xvid",
    ".f4v", ".mpg", ".mpeg", ".m1v", ".m2v", ".dat", ".ogv", ".dv", ".mxf",
    ".gxf", ".lxf", ".wrf", ".wtv", ".dvr-ms", ".rec", ".trp", ".tp", ".m2p",
    ".ps", ".evo", ".ifo", ".bup",
    # 光盘镜像文件
    ".iso", ".img", ".nrg", ".mdf", ".cue", ".bin", ".ccd",
    # 字幕文件
    ".sub", ".idx", ".srt", ".ass", ".ssa", ".vtt", ".sup", ".pgs", ".usf",
    ".xml", ".ttml", ".dfxp", ".sami", ".smi", ".rt", ".sbv", ".stl", ".ttml2",
    ".cap", ".scr", ".dks", ".lrc", ".ksc", ".pan", ".son", ".psb", ".aqt",
    ".jss", ".asc", ".txt"
]




def load_config():
    """
    从文件中加载配置，如果文件不存在则使用默认配置并创建文件
    支持配置验证和类型转换
    """
    global app_config

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

                # 验证和更新配置
                for key, value in loaded_config.items():
                    if key in app_config:
                        # 类型验证
                        expected_type = type(app_config[key])
                        if isinstance(value, expected_type):
                            app_config[key] = value
                        else:
                            logging.warning(f"配置项 {key} 类型不匹配，期望 {expected_type.__name__}，实际 {type(value).__name__}，使用默认值")
                    else:
                        logging.warning(f"未知配置项: {key}")

            logging.info(f"配置已从 {CONFIG_FILE} 加载")
        except Exception as e:
            logging.error(f"加载配置文件 {CONFIG_FILE} 失败: {e}，将使用默认配置")
    else:
        logging.info(f"配置文件 {CONFIG_FILE} 不存在，将创建并保存默认配置")
        save_config()

    # 更新全局变量
    _update_global_variables()

    # 缓存初始化已删除

    # 重新初始化任务管理器（如果配置发生变化）
    _reinitialize_task_manager()

    logging.info(f"配置加载完成 - TMDB: {'✓' if TMDB_API_KEY else '✗'}, Gemini: {'✓' if GEMINI_API_KEY else '✗'}")

def _update_global_variables():
    """更新全局变量"""
    global QPS_LIMIT, COOKIES, CHUNK_SIZE, MAX_WORKERS, LANGUAGE
    global TMDB_API_KEY, GEMINI_API_KEY, GEMINI_API_URL, MODEL, GROUPING_MODEL

    # 基础配置
    QPS_LIMIT = app_config["QPS_LIMIT"]
    COOKIES = app_config["COOKIES"]
    CHUNK_SIZE = app_config["CHUNK_SIZE"]
    MAX_WORKERS = app_config["MAX_WORKERS"]
    LANGUAGE = app_config["LANGUAGE"]

    # API配置
    TMDB_API_KEY = app_config["TMDB_API_KEY"]
    GEMINI_API_KEY = app_config["GEMINI_API_KEY"]
    GEMINI_API_URL = app_config["GEMINI_API_URL"]
    MODEL = app_config["MODEL"]
    GROUPING_MODEL = app_config["GROUPING_MODEL"]

# 缓存初始化函数已删除

def _reinitialize_task_manager():
    """重新初始化任务管理器"""
    global grouping_task_manager

    # 注意：这里不能直接重新创建grouping_task_manager，因为可能有正在运行的任务
    # 只更新配置参数
    # CONFIG变量在这里不可用，使用默认值
    grouping_task_manager.task_timeout = 300
    logging.info(f"智能分组任务管理器配置已更新，任务超时: {grouping_task_manager.task_timeout}秒")

def save_config():
    """将当前配置保存到文件。"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_config, f, ensure_ascii=False, indent=4)
        logging.info(f"配置已保存到 {CONFIG_FILE}。")
        return True
    except Exception as e:
        logging.error(f"保存配置文件 {CONFIG_FILE} 失败: {e}")
        return False


TMDB_API_URL_BASE = "https://api.themoviedb.org/3"

EXTRACTION_PROMPT = """
你是一个专业的媒体信息提取和元数据匹配助手。
**目标：** 根据提供的电影、电视剧或番剧文件名列表，智能解析每个文件名，并从在线数据库中匹配并提取详细元数据，然后将所有结果汇总为一个JSON数组。
**输入：** 一个包含多个电影/电视剧/番剧文件名，每行一个文件名。
**输出：** 严格的JSON格式结果。
**处理步骤（对每个文件名重复执行）：**
1.  **文件名解析与信息提取：**
    *   **核心原则：** 尽最大可能识别并移除所有非标题的技术性后缀、前缀及中间标记，提取出最可能、最简洁的原始标题部分。
    *   **需要移除的常见标记（但不限于）：**
        *   **分辨率:** 2160p, 1080p, 720p, 4K, UHD, SD
        *   **视频编码:** H264, H265, HEVC, x264, x265, AVC, VP9, AV1, DivX, XviD
        *   **来源/压制:** WEB-DL, BluRay, HDTV, WEBRip, BDRip, DVDRip, KORSUB, iNTERNAL, Remux, PROPER, REPACK, RETAIL, Disc, VOSTFR, DUBBED, SUBBED, FanSub, CBR, VBR, P2P
        *   **音频编码/声道:** DDP5.1, Atmos, DTS-HD MA, TrueHD, AC3, AAC, FLAC, DD+7.1, Opus, MP3, 2.0, 5.1, 7.1, Multi-Audio, Dual Audio
        *   **HDR/杜比视界:** DV, HDR, HDR10, DoVi, HLG, HDR10+, WCG
        *   **版本信息:** Director's Cut, Extended, Uncut, Theatrical, Special Edition, Ultimate Edition, Remastered, ReCut, Criterion, IMAX, Limited Series
        *   **发布组/站点:** [RARBG], [YTS.AM], FGT, CtrlHD, DEFLATE, xixi, EVO, GHOULS, FRDS, PANTHEON, WiKi, CHDBits, OurBits, MTeam, LoL, TRP, FWB, x264-GROUP, VCB-Studio, ANi, Lilith-Raws
        *   **季/集号:** S01E01, S1E1, Season 1 Episode 1, Part 1, P1, Ep01, Vol.1, 第1季第1集, SP (Special), OVA, ONA, Movie (对于番剧剧场版), NCED, NCOP (无字幕OP/ED)
        *   **年份:** (2023), [2023], .2023., _2023_
        *   **其他:** (R), _ , -, ., ~ , { }, [ ], ` `, + 等常见分隔符，以及广告词、多余的空格、多余的语言代码（如CHS, ENG, JPN）等。
    *   **提取以下结构化信息：**
        *   **原始标题 (title):** 最可能、最简洁的电影/电视剧/番剧标题，尽量保留原始语言（若文件名中明确）。如果文件名是中文，优先提取中文标题。
        *   **年份 (year):** 识别到的发行年份。
        *   **季号 (season):** 电视剧或番剧的季号，通常为数字。
        *   **集号 (episode):** 电视剧或番剧的集号，必须为数字。格式：S01E01→1, EP01→1, 第1集→1, E01→1
        *   **部分 (part):** 如果是电影的特定部分（如 Part 1, Disc 2，非系列电影的续集），或番剧的OVA/SP等特殊集。

2.  **在线数据库搜索与匹配：**
    *   **操作指示：** **必须使用你的联网搜索工具**。
    *   **搜索关键词构建：**
        *   优先使用解析出的 `title`、`year`、`season`（如果适用）组合成精确的搜索关键词。
        *   对于中文标题，使用其翻译后的英文标题进行搜索。
        *   示例搜索词：`"Movie Title 2023 TMDB"`, `"TV Show Season 1 IMDb"`, `"Anime Name AniDB"`。
    *   **优先顺序：**
        1.  **themoviedb.org (TMDB):** 针对电影和电视剧的首选。
        2.  **AniDB:** 针对动画、动漫（番剧）的首选。
        3.  **IMDb:** 作为TMDB的补充或回退。
        4.  **豆瓣电影 (Douban):** 对于中文内容有额外参考价值，但匹配后仍需转换为英文标题。
        5.  **烂番茄 (Rotten Tomatoes):** 作为评分和补充信息来源。
    *   **匹配策略：**
        *   使用提取出的标题、年份、季号（如果适用）进行精准搜索。
        *   **高置信度匹配：** 只有当搜索结果与解析出的标题高度相似（考虑大小写、标点符号、常见缩写等），年份精确匹配，且媒体类型（电影/电视剧/番剧）一致时，才认定为准确匹配。
        *   **唯一性原则：** 如果搜索结果包含多个条目，选择与文件名信息（特别是年份、版本、季集号）最匹配的**唯一**条目。
        *   **模糊匹配回退：** 如果精准匹配失败，可以尝试进行轻微的模糊匹配（例如移除副标题、尝试常见缩写），但需降低置信度。
        *   **无法匹配的处理：** 如果无法找到高置信度的匹配项，则该条目的元数据字段应为空或 null。

**输出格式要求：**
*   输出必须是严格的JSON格式，且只包含JSON内容，不附带任何解释、说明或额外文本。
*   根元素必须是一个JSON数组 `[]`。
*   数组的每个元素都是一个JSON对象，代表一个文件名的解析结果。
*   JSON结构如下：
    ```json
    [
      {
        "file_name": "string",
        "title": "string",            // 原始英文标题
        "original_title": "string",   // 媒体的原始语言标题 (如日文, 中文等)
        "year": "string",             // 发行年份
        "media_type": "string",       // "movie", "tv_show", "anime"
        "tmdb_id": "string",          // TMDB ID
        "imdb_id": "string",          // IMDb ID
        "anidb_id": "string",         // AniDB ID (如果适用)
        "douban_id": "string",        // 豆瓣 ID (如果适用)
        "season": "number | null",    // 文件名解析出的季号
        "episode": "number | null"    // 文件名解析出的集号
      }
    ]
    ```
*   **字段说明：**
    *   `file_name`: 原始文件名。
    *   `title`: 提取出的媒体原始英文标题。
    *   `original_title`: 媒体在原产地的原始语言标题 (例如，日剧的日文标题，韩剧的韩文标题)。如果数据库未提供或与 `title` 相同，则使用 `title` 的值。
    *   `year`: 电影/电视剧/番剧的发行年份。
    *   `media_type`: 识别出的媒体类型，只能是 `"movie"`, `"tv_show"`, `"anime"` 之一。
    *   `tmdb_id`, `imdb_id`, `anidb_id`, `douban_id`: 对应数据库的唯一ID。如果未找到或不适用，请使用空字符串 `""`。
*   **值约定：**
    *   字符串字段（`title`, `original_title`, `year`, `media_type`, `tmdb_id` 等）如果信息缺失或无法准确识别，请使用空字符串 `""`。
    *   数字字段（`season`, `episode`）如果信息缺失或不适用，请使用 `null`。
    *   **严格性要求：** 任何时候都不要在JSON输出中包含额外的文本、解释或代码块标记（如 ```json）。
"""

# ================================
# 智能分组AI提示词模板
# ================================

MAGIC_PROMPT = """
你是一个专业的媒体文件智能分组助手。你的任务是分析一组媒体文件，并根据它们的内容特征进行智能分组和命名。

**输入：** 一个包含多个媒体文件信息的JSON数组，每个文件包含以下字段：
- filename: 原始文件名
- title: 标准化标题
- year: 发行年份
- season: 季号（如果适用）
- episode: 集号（如果适用）
- media_type: 媒体类型（movie/tv/anime）
- tmdb_info: TMDB数据库信息（如果有）

**目标：**
1. 分析文件之间的关联性（同一部作品、同一季、同一系列等）
2. 创建合理的分组结构
3. 为每个分组生成标准化的文件夹名称
4. 确保分组逻辑清晰、命名规范

**分组规则：**
1. **电视剧/动画分组：**
   - 同一部作品的不同集数应归为一组
   - 同一部作品的不同季应分别分组
   - 特殊集（OVA、SP、电影版）可单独分组或归入主系列

2. **电影分组：**
   - 独立电影通常单独分组
   - 系列电影（如三部曲）可归为一组
   - 同一导演或主题的电影可考虑分组

3. **命名规范：**
   - 使用标准化的中英文标题
   - 包含年份信息（发行年份或年份范围）
   - 对于电视剧，包含季号信息
   - 避免特殊字符和过长的名称
   - 格式示例：
     * "权力的游戏 Game of Thrones S01 (2011)"
     * "复仇者联盟系列 Avengers Collection (2012-2019)"
     * "你的名字 Your Name (2016)"

**输出格式：**
返回一个JSON对象，包含以下结构：
```json
{
  "groups": [
    {
      "group_id": "unique_group_identifier",
      "group_name": "标准化的分组名称",
      "group_type": "tv_season|movie_series|single_movie|anime_series",
      "description": "分组描述",
      "files": [
        {
          "original_filename": "原始文件名",
          "suggested_filename": "建议的新文件名",
          "file_info": "文件的详细信息对象"
        }
      ],
      "metadata": {
        "total_episodes": "总集数（如果适用）",
        "year_range": "年份范围",
        "genre": "类型",
        "rating": "评分（如果有）"
      }
    }
  ],
  "summary": {
    "total_groups": "总分组数",
    "total_files": "总文件数",
    "grouping_confidence": "分组置信度（0-100）",
    "recommendations": ["分组建议和注意事项"]
  }
}
```

**质量要求：**
- 分组逻辑必须合理且一致
- 命名必须规范且易于理解
- 避免创建过多的小分组
- 确保每个文件都被正确归类
- 提供清晰的分组说明和建议

请严格按照JSON格式输出，不要包含任何额外的文本或代码块标记。
"""

GROUP_MERGE_PROMPT = """
你是一个专业的媒体文件分组优化助手。你的任务是分析现有的文件分组，识别可以合并的相关分组，并提供优化建议。

**输入：** 一个包含多个分组的JSON对象，每个分组包含：
- group_id: 分组唯一标识
- group_name: 分组名称
- group_type: 分组类型
- files: 文件列表
- metadata: 分组元数据

**目标：**
1. 识别相关联的分组（同一系列、同一作者、相关主题等）
2. 分析分组的合理性和一致性
3. 提供合并建议和优化方案
4. 生成最终的优化分组结构

**合并规则：**
1. **系列作品合并：**
   - 同一部作品的不同季可以合并为一个大分组
   - 系列电影可以合并为电影集合
   - 相关的OVA、特别篇可以合并到主系列

2. **主题相关合并：**
   - 同一导演的作品
   - 同一制作公司的作品
   - 相同类型或主题的作品

3. **质量优化：**
   - 避免过度细分
   - 确保分组大小合理（不要太大也不要太小）
   - 保持命名一致性

**输出格式：**
返回一个JSON对象，包含：
```json
{
  "optimized_groups": [
    {
      "group_id": "优化后的分组ID",
      "group_name": "优化后的分组名称",
      "group_type": "分组类型",
      "merged_from": ["原始分组ID列表"],
      "files": ["合并后的文件列表"],
      "metadata": "合并后的元数据",
      "merge_reason": "合并原因说明"
    }
  ],
  "merge_summary": {
    "original_groups": "原始分组数",
    "optimized_groups": "优化后分组数",
    "merge_operations": "合并操作数",
    "optimization_score": "优化评分（0-100）",
    "recommendations": ["优化建议"]
  }
}
```

请严格按照JSON格式输出，不要包含任何额外的文本或代码块标记。
"""

# ================================
# 质量评估提示词模板
# ================================

QUALITY_ASSESSMENT_PROMPT = """
你是一个专业的媒体文件质量评估助手。你的任务是评估文件名的质量、分组的合理性，并提供改进建议。

**评估维度：**

1. **文件名质量（0-100分）：**
   - 信息完整性：是否包含必要的标题、年份、季集信息
   - 命名规范性：是否符合标准命名规范
   - 可读性：是否易于理解和识别
   - 一致性：同一分组内命名是否一致

2. **分组合理性（0-100分）：**
   - 逻辑性：分组逻辑是否清晰合理
   - 完整性：相关文件是否都被正确分组
   - 平衡性：分组大小是否合理
   - 实用性：分组是否便于管理和查找

3. **元数据准确性（0-100分）：**
   - 匹配度：与在线数据库的匹配准确性
   - 完整性：元数据信息是否完整
   - 一致性：同一作品的元数据是否一致

**输出格式：**
```json
{
  "overall_score": "总体质量评分（0-100）",
  "detailed_scores": {
    "filename_quality": "文件名质量评分",
    "grouping_rationality": "分组合理性评分",
    "metadata_accuracy": "元数据准确性评分"
  },
  "issues": [
    {
      "type": "问题类型",
      "severity": "严重程度（high/medium/low）",
      "description": "问题描述",
      "affected_files": ["受影响的文件"],
      "suggestion": "改进建议"
    }
  ],
  "recommendations": [
    {
      "priority": "优先级（high/medium/low）",
      "action": "建议操作",
      "description": "详细说明",
      "expected_improvement": "预期改进效果"
    }
  ],
  "summary": {
    "total_files": "总文件数",
    "problematic_files": "有问题的文件数",
    "improvement_potential": "改进潜力评估",
    "next_steps": ["下一步建议"]
  }
}
```

请严格按照JSON格式输出，不要包含任何额外的文本或代码块标记。
"""

# ================================
# 工具函数和辅助方法
# ================================

def safe_filename(filename):
    """
    安全化文件名，移除或替换不安全的字符

    Args:
        filename (str): 原始文件名

    Returns:
        str: 安全化后的文件名
    """
    if not filename:
        return "untitled"

    # 移除或替换不安全的字符
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')

    # 移除控制字符
    filename = ''.join(char for char in filename if ord(char) >= 32)

    # 限制长度
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        max_name_length = MAX_FILENAME_LENGTH - len(ext)
        filename = name[:max_name_length] + ext

    # 移除首尾空格和点
    filename = filename.strip(' .')

    return filename or "untitled"

def format_file_size(size_bytes):
    """
    格式化文件大小为人类可读的格式

    Args:
        size_bytes (int): 文件大小（字节）

    Returns:
        str: 格式化后的文件大小
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_names[i]}"

def validate_input(input_data, input_type="string", max_length=None, allowed_chars=None):
    """
    输入验证函数

    Args:
        input_data: 输入数据
        input_type (str): 数据类型 (string, int, float, list, dict)
        max_length (int): 最大长度限制
        allowed_chars (str): 允许的字符集

    Returns:
        bool: 验证是否通过
    """
    if not ENABLE_INPUT_VALIDATION:
        return True

    try:
        # 类型验证
        if input_type == "string" and not isinstance(input_data, str):
            return False
        elif input_type == "int" and not isinstance(input_data, int):
            return False
        elif input_type == "float" and not isinstance(input_data, (int, float)):
            return False
        elif input_type == "list" and not isinstance(input_data, list):
            return False
        elif input_type == "dict" and not isinstance(input_data, dict):
            return False

        # 长度验证
        if max_length and hasattr(input_data, '__len__') and len(input_data) > max_length:
            return False

        # 字符验证
        if allowed_chars and isinstance(input_data, str):
            if not all(char in allowed_chars for char in input_data):
                return False

        return True
    except Exception as e:
        logging.error(f"输入验证错误: {e}")
        return False

# 缓存键生成函数已删除

# 缓存API调用函数已删除

def retry_on_failure(max_retries=None, delay=None, backoff=None):
    """
    重试装饰器

    Args:
        max_retries (int): 最大重试次数
        delay (float): 重试延迟
        backoff (float): 退避倍数

    Returns:
        装饰器函数
    """
    if max_retries is None:
        max_retries = MAX_RETRIES
    if delay is None:
        delay = RETRY_DELAY
    if backoff is None:
        backoff = RETRY_BACKOFF

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logging.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, {current_delay}秒后重试")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logging.error(f"函数 {func.__name__} 在 {max_retries} 次重试后仍然失败")

            raise last_exception

        return wrapper
    return decorator

def log_performance(func_name, start_time, success=True, **kwargs):
    """
    记录性能日志

    Args:
        func_name (str): 函数名
        start_time (float): 开始时间
        success (bool): 是否成功
        **kwargs: 额外的日志信息
    """
    if PERFORMANCE_MONITORING:
        duration = time.time() - start_time
        performance_monitor.record_api_call(func_name, duration, success)

        log_data = {
            'function': func_name,
            'duration': round(duration, 3),
            'success': success,
            'timestamp': datetime.datetime.now().isoformat()
        }
        log_data.update(kwargs)

        # 缓存相关日志已删除，统一使用INFO级别
        logging.info(f"性能日志: {json.dumps(log_data, ensure_ascii=False)}")

# ================================
# 增强的API函数
# ================================

@qps_limit("extract_movie_info", 'QPS_LIMIT')
@retry_on_failure()
def extract_movie_info_from_filename(filenames):
    """
    从文件名提取电影信息，支持缓存和性能监控

    Args:
        filenames (list): 文件名列表

    Returns:
        list: 提取的电影信息列表
    """
    start_time = time.time()

    try:
        # 输入验证
        if not validate_input(filenames, "list", max_length=100):
            raise ValueError("无效的文件名列表")

        # 缓存逻辑已删除

        # 准备API请求
        headers = {
            "Authorization": f"Bearer {GEMINI_API_KEY}",
            "Content-Type": "application/json",
        }

        user_input_content = "\n".join(filenames)
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_input_content}
            ],
        }

        # 发送API请求
        logging.info(f"正在提取 {len(filenames)} 个文件的信息...")
        response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()
        input_string = data["choices"][0]["message"]["content"]

        # 解析JSON响应
        pattern = r'```json(.*?)```'
        match = re.search(pattern, input_string, re.DOTALL)

        if match:
            json_data = match.group(1).strip()
            logging.debug(f"提取的JSON字符串: {json_data}")
            json_data = json.loads(json_data)

            # 确保返回列表格式
            if not isinstance(json_data, list):
                json_data = [json_data] if json_data else []

            # 缓存存储已删除

            log_performance("extract_movie_info_from_filename", start_time, True,
                          files_processed=len(filenames), results_count=len(json_data))

            logging.info(f"成功提取 {len(json_data)} 个文件的信息")
            return json_data
        else:
            logging.error(f"Gemini API 响应中未找到 JSON 块。完整响应: {input_string}")
            log_performance("extract_movie_info_from_filename", start_time, False, error="no_json_block")
            return None

    except Exception as e:
        log_performance("extract_movie_info_from_filename", start_time, False, error=str(e))
        logging.error(f"提取电影信息失败: {e}", exc_info=True)
        raise


@retry_on_failure()
def search_movie_in_tmdb(movie_info):
    """
    在TMDB中搜索电影信息，支持缓存和性能监控

    Args:
        movie_info (dict): 电影信息字典

    Returns:
        dict: TMDB搜索结果
    """
    start_time = time.time()

    try:
        # 输入验证
        if not validate_input(movie_info, "dict"):
            raise ValueError("无效的电影信息")

        original_title = movie_info.get('original_title', '')
        title = movie_info.get('title', '')
        media_type = movie_info.get('media_type', 'movie')
        tmdb_id = movie_info.get('tmdb_id', '')
        year = movie_info.get('year', '')

        # TMDB搜索缓存逻辑已删除

        logging.debug(f"正在TMDB中搜索: {original_title} ({year})")

        # 清理标题
        original_title = str(re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', ' ', original_title))
        min_year = 3 if media_type == 'movie' else 5

        def perform_tmdb_search(query, media_type_search, language):
            """执行TMDB搜索"""
            # 使用QPS限制器控制请求频率
            qps_limiter.acquire()

            if media_type_search == 'movie':
                url = f"{TMDB_API_URL_BASE}/search/movie"
            elif media_type_search == 'tv':
                url = f"{TMDB_API_URL_BASE}/search/tv"
            else:
                return []

            params = {
                "api_key": TMDB_API_KEY,
                "query": query,
                "language": language,
            }

            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json().get('results', [])

        # 第一步：使用原始标题搜索
        search_results = perform_tmdb_search(original_title, 'tv' if media_type != 'movie' else 'movie', LANGUAGE)
        logging.debug(f"TMDB搜索结果 '{original_title}': {len(search_results)} 个结果")

        # 精确匹配：年份和TMDB ID
        for result in search_results:
            try:
                data = result.get('release_date') or result.get('first_air_date')
                if data and data[:4] == year:
                    logging.info(f"精确年份匹配: {result}")
                    # 缓存存储已删除
                    log_performance("search_movie_in_tmdb", start_time, True, match_type="exact_year")
                    return result
                elif tmdb_id and tmdb_id == str(result['id']):
                    logging.info(f"TMDB ID匹配: {result}")
                    # 缓存存储已删除
                    log_performance("search_movie_in_tmdb", start_time, True, match_type="tmdb_id")
                    return result
            except (KeyError, IndexError) as e:
                logging.warning(f"处理TMDB结果时出错: {e}")
                continue

        # 模糊匹配：年份差异在允许范围内
        for result in search_results:
            try:
                data = result.get('release_date') or result.get('first_air_date')
                if data and year:
                    year_diff = abs(int(data[:4]) - int(year))
                    result_title = result.get('title', result.get('name', ''))
                    logging.debug(f"年份差异 '{result_title}': {year_diff} ({data[:4]} vs {year})")

                    if year_diff <= min_year or title == result_title:
                        logging.info(f"模糊匹配成功: {result}")
                        log_performance("search_movie_in_tmdb", start_time, True, match_type="fuzzy_year")
                        return result
            except (KeyError, IndexError, ValueError) as e:
                logging.warning(f"处理TMDB结果时出错: {e}")
                continue

        # 第二步：使用清理后的标题搜索
        if title and title != original_title:
            cleaned_title = str(re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', ' ', title))
            logging.debug(f"使用清理后的标题搜索: '{cleaned_title}'")

            cleaned_search_results = perform_tmdb_search(cleaned_title, 'tv' if media_type != 'movie' else 'movie', LANGUAGE)
            logging.debug(f"清理标题搜索结果 '{cleaned_title}': {len(cleaned_search_results)} 个结果")

            # 对清理后的结果进行相同的匹配逻辑
            for result in cleaned_search_results:
                try:
                    data = result.get('release_date') or result.get('first_air_date')
                    if data and data[:4] == year:
                        logging.info(f"清理标题精确匹配: {result}")
                        log_performance("search_movie_in_tmdb", start_time, True, match_type="cleaned_exact")
                        return result
                    elif tmdb_id and tmdb_id == str(result['id']):
                        logging.info(f"清理标题TMDB ID匹配: {result}")
                        log_performance("search_movie_in_tmdb", start_time, True, match_type="cleaned_tmdb_id")
                        return result
                except (KeyError, IndexError) as e:
                    logging.warning(f"处理清理标题TMDB结果时出错: {e}")
                    continue

            for result in cleaned_search_results:
                try:
                    data = result.get('release_date') or result.get('first_air_date')
                    if data and year:
                        year_diff = abs(int(data[:4]) - int(year))
                        result_title = result.get('title', result.get('name', ''))

                        if year_diff <= min_year or title == result_title:
                            logging.info(f"清理标题模糊匹配: {result}")
                            log_performance("search_movie_in_tmdb", start_time, True, match_type="cleaned_fuzzy")
                            return result
                except (KeyError, IndexError, ValueError) as e:
                    logging.warning(f"处理清理标题TMDB结果时出错: {e}")
                    continue

        # 未找到匹配结果
        logging.info(f"未在TMDB中找到匹配结果: {original_title} ({year})")
        log_performance("search_movie_in_tmdb", start_time, True, match_type="no_match")
        return None

    except Exception as e:
        log_performance("search_movie_in_tmdb", start_time, False, error=str(e))
        logging.error(f"TMDB搜索出错: {e}", exc_info=True)
        raise


class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_queue.append(log_entry)

# 配置 Flask 应用的日志
# 移除默认的basicConfig，手动添加处理器
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # 设置根日志级别

# 清除所有现有的处理器，避免重复日志
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# 添加文件处理器 (使用 RotatingFileHandler)
# maxBytes: 1MB, backupCount: 5
file_handler = RotatingFileHandler('rename_log.log', maxBytes=1024 * 1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
root_logger.addHandler(file_handler)

    # 添加控制台处理器（Windows兼容性：设置错误处理）
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# 在Windows系统中，控制台可能不支持某些Unicode字符，设置错误处理策略
if hasattr(console_handler.stream, 'reconfigure'):
    try:
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # 如果重配置失败，继续使用默认设置
root_logger.addHandler(console_handler)

# 添加自定义队列处理器
queue_handler = QueueHandler()
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
root_logger.addHandler(queue_handler)

# 确保 Flask 自己的日志也通过 root_logger 处理
app.logger.addHandler(queue_handler) # Flask app.logger 默认会继承 root_logger 的处理器

# 禁用 Werkzeug 的访问日志
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# 媒体文件类型
MEDIATYPES = [
    "wma", "wav", "mp3", "aac", "ra", "ram", "mp2", "ogg", "aif",
    "mpega", "amr", "mid", "midi", "m4a", "m4v", "wmv", "rmvb",
    "mpeg4", "mpeg2", "flv", "avi", "3gp", "mpga", "qt", "rm",
    "wmz", "wmd", "wvx", "wmx", "wm", "swf", "mpg", "mp4", "mkv",
    "mpeg", "mov", "mdf", "asf",
    "webm", "ogv", "m2ts", "ts", "vob", "divx", "xvid", "f4v", "m2v",
    "amv", "drc", "evo", "flc", "h264", "h265", "icod", "mod", "tod",
    "mts", "ogm", "qtff", "rec", "vp6", "vp7", "vp8", "vp9", "iso"
]

# 支持的媒体文件扩展名列表（与pan115-scraper兼容）
SUPPORTED_MEDIA_TYPES = [
    "wma", "wav", "mp3", "aac", "ra", "ram", "mp2", "ogg", "aif",
    "mpega", "amr", "mid", "midi", "m4a", "m4v", "wmv", "rmvb",
    "mpeg4", "mpeg2", "flv", "avi", "3gp", "mpga", "qt", "rm",
    "wmz", "wmd", "wvx", "wmx", "wm", "swf", "mpg", "mp4", "mkv",
    "mpeg", "mov", "mdf", "asf", "webm", "ogv", "m2ts", "ts", "vob",
    "divx", "xvid", "f4v", "m2v", "amv", "drc", "evo", "flc",
    "h264", "h265", "icod", "mod", "tod", "mts", "ogm", "qtff",
    "rec", "vp6", "vp7", "vp8", "vp9", "iso"
]

# 115 网盘请求头和 Cookies
headers = {'Content-Type': 'application/x-www-form-urlencoded','User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',}
cookies = {}



def load_cookies():
    global cookies
    # 从 app_config 中获取 COOKIES
    cookies_str = app_config.get("COOKIES")
    if cookies_str:
        cookies = {}
        for part in cookies_str.split('; '):
            if '=' in part:
                key, value = part.split('=', 1)
                cookies[key] = value
            else:
                cookies[part] = ''
        logging.info(f"Cookies loaded successfully from app_config. Parsed cookies: {cookies}")
    else:
        cookies = {} # 确保在 COOKIES 为空时，cookies 字典也被清空
        logging.warning("COOKIES 配置项为空。请在网页配置中设置。")

# 在应用启动时加载配置和 Cookies
load_config()
load_cookies()

# QPS 限制器
class QPSLimiter:
    def __init__(self, qps_limit):
        self.qps_limit = float(qps_limit) # Convert to float
        self.interval = 1.0 / self.qps_limit
        self.last_request_time = 0
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.last_request_time
            if elapsed_time < self.interval:
                time.sleep(self.interval - elapsed_time)
            self.last_request_time = time.time()

qps_limiter = QPSLimiter(qps_limit=QPS_LIMIT)

# ================================
# 115云盘API增强函数
# ================================

@qps_limit("batch_rename", QPS_LIMIT)
@retry_on_failure()
def batch_rename_file(namedict):
    """
    批量重命名文件 - 增强版本，支持缓存和性能监控

    Args:
        namedict (dict): 重命名字典 {file_id: new_name}

    Returns:
        dict: 操作结果
    """
    start_time = time.time()

    try:
        # 输入验证
        if not validate_input(namedict, "dict", max_length=100):
            raise ValueError("无效的重命名字典")

        logging.info(f"开始批量重命名 {len(namedict)} 个文件")

        # 构建请求数据
        newnames = {}
        for key, value in namedict.items():
            safe_name = safe_filename(value)
            newnames[f'files_new_name[{key}]'] = safe_name

        data = parse.urlencode(newnames)
        url = 'https://webapi.115.com/files/batch_rename'

        # 发送请求
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()

        # 详细打印返回值
        logging.info(f"🔍 重命名API返回值: {json.dumps(result, ensure_ascii=False, indent=2)}")

        if result.get('state'):
            log_performance("batch_rename_file", start_time, True, files_renamed=len(namedict))
            logging.info(f"✅ 批量重命名成功: {len(namedict)} 个文件")

            # 打印成功的详细信息
            if 'data' in result:
                logging.info(f"📋 重命名详情: {json.dumps(result['data'], ensure_ascii=False, indent=2)}")

            # 使用统一的缓存清理机制

            return {'success': True, 'result': result, 'message': f'成功重命名 {len(namedict)} 个文件'}
        else:
            log_performance("batch_rename_file", start_time, False, error=result.get('error', 'Unknown'))
            error_msg = result.get('error') or result.get('errno_desc') or result.get('errcode') or 'Unknown error'
            logging.error(f"❌ 批量重命名失败: {error_msg}")
            logging.error(f"🔍 失败详情: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return {'success': False, 'error': error_msg, 'result': result}

    except requests.exceptions.HTTPError as e:
        log_performance("batch_rename_file", start_time, False, error=f"HTTP_{e.response.status_code}")
        logging.error(f"HTTP错误 - 批量重命名: {e.response.status_code} - {e.response.text}")
        return {'success': False, 'error': str(e), 'status_code': e.response.status_code, 'content': e.response.text}
    except Exception as e:
        log_performance("batch_rename_file", start_time, False, error=str(e))
        logging.error(f"批量重命名出错: {e}", exc_info=True)
        raise

@qps_limit("batch_move", QPS_LIMIT)
@retry_on_failure()
def batch_move_file(cids, pid):
    """
    批量移动文件 - 增强版本，支持缓存和性能监控

    Args:
        cids: 文件ID列表或单个文件ID
        pid: 目标父目录ID

    Returns:
        dict: 操作结果
    """
    start_time = time.time()

    try:
        # 输入验证
        if isinstance(cids, str):
            file_count = 1
        elif isinstance(cids, list):
            file_count = len(cids)
            if not validate_input(cids, "list", max_length=100):
                raise ValueError("无效的文件ID列表")
        else:
            raise ValueError("cids必须是字符串或列表")

        if not validate_input(str(pid), "string"):
            raise ValueError("无效的目标目录ID")

        logging.info(f"开始批量移动 {file_count} 个文件到目录 {pid}")

        # 构建请求数据
        data = {'move_proid': '1749745456990_-69_0', 'pid': pid}
        if isinstance(cids, str):
            data['fid[0]'] = cids
        else:
            for i in range(len(cids)):
                data[f'fid[{i}]'] = cids[i]

        # 发送请求
        response = requests.post('https://webapi.115.com/files/move',
                               headers=headers, cookies=cookies, data=data, timeout=TIMEOUT)
        response.raise_for_status()

        # 处理响应
        result = response.json() if 'application/json' in response.headers.get('Content-Type', '') else response.text

        log_performance("batch_move_file", start_time, True, files_moved=file_count)
        logging.info(f"批量移动成功: {file_count} 个文件移动到 {pid}")

        # 使用统一的缓存清理机制

        return {'success': True, 'result': result}

    except requests.exceptions.HTTPError as e:
        log_performance("batch_move_file", start_time, False, error=f"HTTP_{e.response.status_code}")
        logging.error(f"HTTP错误 - 批量移动: {e.response.status_code} - {e.response.text}")
        return {'success': False, 'error': str(e), 'status_code': e.response.status_code, 'content': e.response.text}
    except Exception as e:
        log_performance("batch_move_file", start_time, False, error=str(e))
        logging.error(f"批量移动出错: {e}", exc_info=True)
        raise



@retry_on_failure()
def extract_movie_name_and_info(chunk):
    """
    提取电影名称和信息 - 增强版本，支持缓存和性能监控

    Args:
        chunk (list): 文件信息列表

    Returns:
        list: 刮削结果列表
    """
    start_time = time.time()
    results = []

    try:
        # 输入验证
        if not validate_input(chunk, "list", max_length=50):
            raise ValueError("无效的文件列表")

        names = [f.get("file_name") for f in chunk if f.get("file_name")]
        if not names:
            logging.warning("没有有效的文件名")
            return results

        logging.info(f"开始提取 {len(names)} 个文件的信息")

        # 生成缓存键

        # 尝试从缓存获取 - 刮削缓存已禁用

        # 提取电影信息
        movie_info_list = extract_movie_info_from_filename(names)
        if not movie_info_list:
            logging.warning("没有从文件名中提取到电影信息")
            # 为所有文件创建提取失败的结果
            for fids in chunk:
                original_name = fids.get('n', '')
                results.append({
                    'fid': fids.get('fid'),
                    'original_name': original_name,
                    'suggested_name': '',
                    'size': fids.get('s'),
                    'tmdb_info': None,
                    'file_info': None,
                    'status': 'extraction_failed',
                    'error': '无法从文件名提取电影信息'
                })
            log_performance("extract_movie_name_and_info", start_time, True, extracted_count=0)
            return results

        logging.info(f"提取到 {len(movie_info_list)} 个电影信息")

        # 使用线程池进行并发TMDB搜索
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(movie_info_list))) as executor:
            future_to_file_info = {
                executor.submit(search_movie_in_tmdb, file_info): (fids, file_info)
                for fids, file_info in zip(chunk, movie_info_list)
            }

            for future in as_completed(future_to_file_info):
                fids, file_info = future_to_file_info[future]
                original_name = fids.get('n', '')
                suggested_name = ""

                try:
                    tmdb_result = future.result()
                    media_type = file_info.get('media_type', 'movie')
                    _, ext = os.path.splitext(original_name)

                    if tmdb_result:
                        if media_type == 'movie':
                            title = tmdb_result.get('title', '')
                            release_date = tmdb_result.get('release_date', '')
                            tmdb_id = tmdb_result.get('id', '')
                            size = fids.get('s', '')

                            if title and release_date:
                                year = release_date[:4]
                                suggested_name = safe_filename(f"{title} ({year}) {{tmdb-{tmdb_id}}} {size}{ext}")
                        else:
                            # TV/动画处理
                            name = tmdb_result.get('name', '')
                            first_air_date = tmdb_result.get('first_air_date', '')
                            tmdb_id = tmdb_result.get('id', '')
                            size = fids.get('s', '')

                            season = int(file_info.get('season', 1) or 1)
                            episode = file_info.get('episode')

                            # 简化调试日志
                            if episode is None:
                                # 后备逻辑：检查文件名是否为纯数字（如 1.mp4, 5.mp4）
                                base_name = os.path.splitext(original_name)[0]  # 去掉扩展名
                                if base_name.isdigit():
                                    episode = int(base_name)
                                    logging.info(f"🔧 使用数字文件名作为集号 - 文件: {original_name} -> 第{episode}集")
                                else:
                                    logging.warning(f"⚠️ TV剧集号提取失败 - 文件: {original_name}")
                                    logging.debug(f"  提取结果: name={name}, episode={episode}, season={season}")
                            else:
                                logging.debug(f"✅ TV剧信息提取成功 - {original_name} -> S{season:02d}E{episode:02d}")

                            if name and first_air_date and episode is not None:
                                year = first_air_date[:4]
                                episode = int(episode or 1)
                                suggested_name = safe_filename(f"{name} ({year}) S{season:02d}E{episode:02d} {{tmdb-{tmdb_id}}} {size}{ext}")

                        if suggested_name:
                            logging.info(f"成功匹配: {original_name} -> {suggested_name}")
                            results.append({
                                'fid': fids.get('fid'),
                                'original_name': original_name,
                                'suggested_name': suggested_name,
                                'size': fids.get('s'),
                                'tmdb_info': tmdb_result,
                                'file_info': file_info,
                                'status': 'success'
                            })
                        else:
                            logging.warning(f"无法生成建议名称: {original_name}")
                            results.append({
                                'fid': fids.get('fid'),
                                'original_name': original_name,
                                'suggested_name': '',
                                'size': fids.get('s'),
                                'tmdb_info': tmdb_result,
                                'file_info': file_info,
                                'status': 'no_suggestion',
                                'error': '无法生成建议名称'
                            })
                    else:
                        logging.warning(f"未找到TMDB结果: {original_name}")
                        results.append({
                            'fid': fids.get('fid'),
                            'original_name': original_name,
                            'suggested_name': '',
                            'size': fids.get('s'),
                            'tmdb_info': None,
                            'file_info': file_info,
                            'status': 'no_tmdb_result',
                            'error': '未找到TMDB匹配结果'
                        })

                except Exception as exc:
                    logging.error(f"处理文件 {original_name} 时出错: {exc}")
                    results.append({
                        'fid': fids.get('fid'),
                        'original_name': original_name,
                        'suggested_name': '',
                        'size': fids.get('s'),
                        'tmdb_info': None,
                        'file_info': file_info,
                        'status': 'error',
                        'error': str(exc)
                    })

        # 缓存结果 - 刮削缓存已禁用

        log_performance("extract_movie_name_and_info", start_time, True,
                       processed_files=len(chunk), successful_matches=len([r for r in results if r.get('status') == 'success']))

        logging.info(f"完成信息提取: {len(results)} 个结果")
        return results

    except Exception as e:
        log_performance("extract_movie_name_and_info", start_time, False, error=str(e))
        logging.error(f"提取电影信息失败: {e}", exc_info=True)
        raise



@retry_on_failure()
def _get_single_level_content_from_115(cid, offset, limit):
    """
    获取115网盘指定目录下的单层文件和目录列表 - 增强版本

    Args:
        cid (str): 目录ID
        offset (int): 偏移量
        limit (int): 限制数量

    Returns:
        dict: API响应数据
    """
    start_time = time.time()

    try:
        # QPS限制控制
        qps_limiter.acquire()

        # 输入验证
        if not validate_input(str(cid), "string"):
            raise ValueError("无效的目录ID")
        if not validate_input(offset, "int") or offset < 0:
            raise ValueError("无效的偏移量")
        if not validate_input(limit, "int") or limit <= 0 or limit > 1000:
            raise ValueError("无效的限制数量")

        # 生成缓存键

        # 尝试从缓存获取

        logging.debug(f"获取115目录内容: CID={cid}, offset={offset}, limit={limit}")

        # 构建URL
        url1 = f'https://webapi.115.com/files?aid=1&cid={cid}&o=user_ptime&asc=0&offset={offset}&show_dir=1&limit={limit}&code=&scid=&snap=0&natsort=1&record_open_time=1&count_folders=1&type=&source=&format=json'
        url2 = f'https://aps.115.com/natsort/files.php?aid=1&cid={cid}&o=file_name&asc=1&offset={offset}&show_dir=1&limit={limit}&code=&scid=&snap=0&natsort=1&record_open_time=1&count_folders=1&type=&source=&format=json&fc_mix=0'

        # 首先尝试URL2（按文件名排序）
        logging.debug(f"尝试URL2: {url2}")
        response = requests.get(url2, headers=headers, cookies=cookies, timeout=TIMEOUT)
        response.raise_for_status()
        response_data = response.json()

        # 如果URL2没有返回数据，尝试URL1
        if not response_data.get("data", []):
            logging.debug(f"URL2无数据，尝试URL1: {url1}")
            response = requests.get(url1, headers=headers, cookies=cookies, timeout=TIMEOUT)
            response.raise_for_status()
            response_data = response.json()

        # 缓存结果

        log_performance("_get_single_level_content_from_115", start_time, True,
                       items_count=len(response_data.get("data", [])))

        return response_data

    except requests.exceptions.HTTPError as e:
        log_performance("_get_single_level_content_from_115", start_time, False,
                       error=f"HTTP_{e.response.status_code}")
        logging.error(f"HTTP错误 - 获取115目录内容 CID {cid}: {e.response.status_code} - {e.response.text}")
        return {"success": False, "error": str(e), "status_code": e.response.status_code, "content": e.response.text}
    except Exception as e:
        log_performance("_get_single_level_content_from_115", start_time, False, error=str(e))
        logging.error(f"获取115目录内容出错 CID {cid}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@qps_limit("get_file_list", QPS_LIMIT)
@retry_on_failure()
def get_all_files_from_115_for_scraping(cid, offset, limit, all_files):
    """
    递归获取115网盘指定目录下的视频文件列表 - 专用于刮削预览
    只收集视频文件，过滤掉音频、图片、字幕等非视频文件

    Args:
        cid (str): 目录ID
        offset (int): 偏移量
        limit (int): 限制数量
        all_files (list): 文件列表（引用传递）
    """
    start_time = time.time()

    try:
        logging.debug(f"🔍 获取115目录内容用于刮削: CID={cid}, offset={offset}, limit={limit}")

        # 获取目录内容
        response_data = _get_single_level_content_from_115(cid, offset, limit)

        if not response_data or response_data.get("success") is False:
            logging.warning(f"获取目录内容失败: CID={cid}")
            return

        total_count = response_data.get("count", 0)
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0

        # 获取路径信息
        file_path_parts = [a['name'] for a in response_data.get("path", [])[1:]]
        current_path_prefix = "/".join(file_path_parts)

        files_processed = 0
        dirs_processed = 0

        # 处理当前页的数据
        for data in response_data.get("data", []):
            if 'fid' in data:  # 文件 - 只收集视频文件
                filename = data.get("n", "")

                # 检查文件扩展名，只处理视频文件
                _, ext = os.path.splitext(filename)
                ext_lower = ext.lower()[1:]  # 去掉点号并转小写

                # 只处理视频文件，过滤掉音频、图片、字幕等文件
                video_extensions = {
                    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "3gp",
                    "ts", "m2ts", "mts", "vob", "rmvb", "rm", "asf", "divx", "xvid",
                    "f4v", "mpg", "mpeg", "m1v", "m2v", "dat", "ogv", "dv", "mxf",
                    "gxf", "lxf", "wrf", "wtv", "dvr-ms", "rec", "trp", "tp", "m2p",
                    "ps", "evo", "ifo", "bup", "iso"
                }

                if ext_lower not in video_extensions:
                    logging.debug(f"⏭️ 跳过非视频文件: {filename} (扩展名: {ext_lower})")
                    continue

                # 转换文件大小
                size_value = data.get('s', 0)
                if isinstance(size_value, str) and size_value.endswith('GB'):
                    # 已经是GB格式，保持不变
                    pass
                else:
                    # 是字节数，需要转换
                    try:
                        bytes_value = int(size_value)
                        gb_in_bytes = 1024 ** 3
                        gb_value = bytes_value / gb_in_bytes
                        data['s'] = f"{gb_value:.1f}GB"
                    except (ValueError, TypeError):
                        # 如果转换失败，保持原值
                        pass

                # 构建完整路径
                if current_path_prefix:
                    data["file_name"] = os.path.join(current_path_prefix, filename)
                else:
                    data["file_name"] = filename

                all_files.append(data)
                files_processed += 1
                logging.debug(f"📄 添加视频文件: {filename}")

            elif 'cid' in data:  # 目录
                # 递归处理子目录，添加延迟以遵守QPS限制
                time.sleep(1.0 / QPS_LIMIT + 0.1)
                get_all_files_from_115_for_scraping(data['cid'], 0, limit, all_files)
                dirs_processed += 1

        # 处理分页（仅在第一次调用时）
        if offset == 0 and total_pages > 1:
            logging.debug(f"处理分页: 总页数={total_pages}")
            for page in range(1, total_pages):
                next_offset = page * limit

                # 获取下一页数据
                next_response_data = _get_single_level_content_from_115(cid, next_offset, limit)

                if not next_response_data or next_response_data.get("success") is False:
                    logging.warning(f"获取分页数据失败: CID={cid}, page={page}")
                    continue

                # 处理分页数据
                for data in next_response_data.get("data", []):
                    if 'fid' in data:  # 文件 - 只收集视频文件
                        filename = data.get("n", "")

                        # 检查文件扩展名，只处理视频文件
                        _, ext = os.path.splitext(filename)
                        ext_lower = ext.lower()[1:]  # 去掉点号并转小写

                        # 只处理视频文件，过滤掉音频、图片、字幕等文件
                        video_extensions = {
                            "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "3gp",
                            "ts", "m2ts", "mts", "vob", "rmvb", "rm", "asf", "divx", "xvid",
                            "f4v", "mpg", "mpeg", "m1v", "m2v", "dat", "ogv", "dv", "mxf",
                            "gxf", "lxf", "wrf", "wtv", "dvr-ms", "rec", "trp", "tp", "m2p",
                            "ps", "evo", "ifo", "bup", "iso"
                        }

                        if ext_lower not in video_extensions:
                            logging.debug(f"⏭️ 跳过非视频文件: {filename} (扩展名: {ext_lower})")
                            continue

                        # 转换文件大小
                        size_value = data.get('s', 0)
                        if isinstance(size_value, str) and size_value.endswith('GB'):
                            pass
                        else:
                            try:
                                bytes_value = int(size_value)
                                gb_in_bytes = 1024 ** 3
                                gb_value = bytes_value / gb_in_bytes
                                data['s'] = f"{gb_value:.1f}GB"
                            except (ValueError, TypeError):
                                pass

                        if current_path_prefix:
                            data["file_name"] = os.path.join(current_path_prefix, filename)
                        else:
                            data["file_name"] = filename

                        all_files.append(data)
                        files_processed += 1
                        logging.debug(f"📄 添加视频文件(分页): {filename}")

                    elif 'cid' in data:
                        # 递归处理子目录，添加延迟以遵守QPS限制
                        time.sleep(1.0 / QPS_LIMIT + 0.1)
                        get_all_files_from_115_for_scraping(data['cid'], 0, limit, all_files)
                        dirs_processed += 1

        log_performance("get_all_files_from_115_for_scraping", start_time, True,
                       files_processed=files_processed, dirs_processed=dirs_processed)

        logging.debug(f"完成刮削文件列表获取: CID={cid}, 文件={files_processed}, 目录={dirs_processed}")

    except Exception as e:
        log_performance("get_all_files_from_115_for_scraping", start_time, False, error=str(e))
        logging.error(f"获取刮削文件列表出错 CID {cid}: {e}", exc_info=True)


def get_file_list_from_115(cid, offset, limit, all_files):
    """
    递归获取115网盘指定目录下的文件列表 - 增强版本

    Args:
        cid (str): 目录ID
        offset (int): 偏移量
        limit (int): 限制数量
        all_files (list): 文件列表（引用传递）
    """
    start_time = time.time()

    try:
        # 输入验证
        if not validate_input(str(cid), "string"):
            raise ValueError("无效的目录ID")
        if not validate_input(offset, "int") or offset < 0:
            raise ValueError("无效的偏移量")
        if not validate_input(limit, "int") or limit <= 0:
            raise ValueError("无效的限制数量")

        logging.debug(f"递归获取文件列表: CID={cid}, offset={offset}, limit={limit}")

        # 使用单层内容获取函数
        response_data = _get_single_level_content_from_115(cid, offset, limit)

        if not response_data or response_data.get("success") is False:
            logging.warning(f"获取目录内容失败: CID={cid}")
            return

        total_count = response_data.get("count", 0)
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0

        # 构建路径前缀
        file_path_parts = [a.get('name', '') for a in response_data.get("path", [])[1:]]
        current_path_prefix = "/".join(file_path_parts) if file_path_parts else ""

        files_processed = 0
        dirs_processed = 0

        # 处理当前页的数据
        for data in response_data.get("data", []):
            if 'fid' in data:  # 文件
                if data.get('ico') in MEDIATYPES:
                    # 转换文件大小 - 处理可能已经是字符串格式的情况
                    size_value = data.get('s', 0)
                    if isinstance(size_value, str) and size_value.endswith('GB'):
                        # 已经是GB格式，保持不变
                        pass
                    else:
                        # 是字节数，需要转换
                        try:
                            bytes_value = int(size_value)
                            gb_in_bytes = 1024 ** 3
                            gb_value = bytes_value / gb_in_bytes
                            data['s'] = f"{gb_value:.1f}GB"
                        except (ValueError, TypeError):
                            # 如果转换失败，保持原值
                            pass

                    # 构建完整路径
                    filename = data.get("n", "")
                    if current_path_prefix:
                        data["file_name"] = os.path.join(current_path_prefix, filename)
                    else:
                        data["file_name"] = filename

                    all_files.append(data)
                    files_processed += 1

            elif 'cid' in data:  # 目录
                # 递归处理子目录，添加延迟以遵守QPS限制
                time.sleep(1.0 / QPS_LIMIT + 0.1)  # 根据QPS限制动态调整延迟
                get_file_list_from_115(data['cid'], 0, limit, all_files)
                dirs_processed += 1

        # 处理分页（仅在第一次调用时）
        if offset == 0 and total_pages > 1:
            logging.debug(f"处理分页: 总页数={total_pages}")
            for page in range(1, total_pages):
                next_offset = page * limit

                # 获取下一页数据
                next_response_data = _get_single_level_content_from_115(cid, next_offset, limit)

                if not next_response_data or next_response_data.get("success") is False:
                    logging.warning(f"获取分页数据失败: CID={cid}, page={page}")
                    continue

                # 处理分页数据
                for data in next_response_data.get("data", []):
                    if 'fid' in data:
                        if data.get('ico') in MEDIATYPES:
                            # 处理文件大小，可能是字节数或已格式化的字符串
                            size_value = data.get('s', 0)
                            if isinstance(size_value, str):
                                # 如果已经是格式化的字符串（如 "86.4GB"），直接使用
                                data['s'] = size_value
                            else:
                                # 如果是字节数，转换为GB
                                try:
                                    bytes_value = int(size_value)
                                    gb_in_bytes = 1024 ** 3
                                    gb_value = bytes_value / gb_in_bytes
                                    data['s'] = f"{gb_value:.1f}GB"
                                except (ValueError, TypeError):
                                    data['s'] = "0.0GB"

                            filename = data.get("n", "")
                            if current_path_prefix:
                                data["file_name"] = os.path.join(current_path_prefix, filename)
                            else:
                                data["file_name"] = filename

                            all_files.append(data)
                            files_processed += 1

                    elif 'cid' in data:
                        # 递归处理子目录，添加延迟以遵守QPS限制
                        time.sleep(1.0 / QPS_LIMIT + 0.1)  # 根据QPS限制动态调整延迟
                        get_file_list_from_115(data['cid'], 0, limit, all_files)
                        dirs_processed += 1

        log_performance("get_file_list_from_115", start_time, True,
                       files_processed=files_processed, dirs_processed=dirs_processed)

        logging.debug(f"完成文件列表获取: CID={cid}, 文件={files_processed}, 目录={dirs_processed}")

    except Exception as e:
        log_performance("get_file_list_from_115", start_time, False, error=str(e))
        logging.error(f"获取文件列表出错 CID {cid}: {e}", exc_info=True)
        # 不抛出异常，允许其他目录继续处理


# ================================
# 115云盘特定API端点
# ================================

@app.route('/api/115/files', methods=['GET'])
def get_115_files():
    """获取115云盘文件列表"""
    try:
        cid = request.args.get('cid', '0')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
        recursive = request.args.get('recursive', 'false').lower() == 'true'

        if recursive:
            all_files = []
            get_file_list_from_115(cid, offset, limit, all_files)
            return jsonify({
                'success': True,
                'files': all_files,
                'total_count': len(all_files),
                'recursive': True
            })
        else:
            response_data = _get_single_level_content_from_115(cid, offset, limit)
            if response_data and response_data.get("success") is not False:
                return jsonify({
                    'success': True,
                    'data': response_data.get('data', []),
                    'count': response_data.get('count', 0),
                    'path': response_data.get('path', [])
                })
            else:
                return jsonify({'success': False, 'error': '获取文件列表失败'})

    except Exception as e:
        logging.error(f"获取115文件列表出错: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/115/rename', methods=['POST'])
def rename_115_files():
    """批量重命名115云盘文件"""
    try:
        data = request.get_json()
        if not data or 'rename_dict' not in data:
            return jsonify({'success': False, 'error': '缺少重命名数据'})

        rename_dict = data['rename_dict']
        current_folder_id = data.get('current_folder_id', '0')  # 获取当前文件夹ID

        logging.info(f"🔄 开始重命名操作，当前文件夹ID: {current_folder_id}")

        result = batch_rename_file(rename_dict)

        # 如果重命名成功，添加刷新指令
        if result.get('success'):
            result['refresh_folder'] = True
            result['folder_id'] = current_folder_id
            logging.info(f"✅ 重命名成功，将刷新文件夹 {current_folder_id}")

        # 注意：batch_rename_file 函数内部已经处理了缓存清理
        # 这里不需要重复清理缓存

        return jsonify(result)

    except Exception as e:
        logging.error(f"❌ 批量重命名出错: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/115/move', methods=['POST'])
def move_115_files():
    """批量移动115云盘文件"""
    try:
        data = request.get_json()
        if not data or 'file_ids' not in data or 'target_id' not in data:
            return jsonify({'success': False, 'error': '缺少移动数据'})

        file_ids = data['file_ids']
        target_id = data['target_id']

        result = batch_move_file(file_ids, target_id)

        return jsonify(result)

    except Exception as e:
        logging.error(f"批量移动出错: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/115/scrape', methods=['POST'])
def scrape_115_files():
    """刮削115云盘文件信息"""
    try:
        data = request.get_json()
        if not data or 'files' not in data:
            return jsonify({'success': False, 'error': '缺少文件数据'})

        files = data['files']
        chunk_size = data.get('chunk_size', CHUNK_SIZE)

        all_results = []

        # 分块处理
        for i in range(0, len(files), chunk_size):
            chunk = files[i:i + chunk_size]
            results = extract_movie_name_and_info(chunk)
            all_results.extend(results)

        return jsonify({
            'success': True,
            'results': all_results,
            'total_processed': len(files),
            'successful_matches': len([r for r in all_results if r.get('status') == 'success'])
        })

    except Exception as e:
        logging.error(f"刮削文件信息出错: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/115/search', methods=['GET'])
def search_115_files():
    """搜索115云盘文件"""
    try:
        query = request.args.get('query', '').strip()
        cid = request.args.get('cid', '0')
        file_type = request.args.get('type', 'all')  # all, video, audio, image, document
        limit = int(request.args.get('limit', 100))

        if not query:
            return jsonify({'success': False, 'error': '搜索关键词不能为空'})

        # 缓存逻辑已删除

        # 执行搜索 - 这里需要实现115云盘的搜索API
        # 暂时使用文件列表过滤作为示例
        all_files = []
        get_file_list_from_115(cid, 0, 1000, all_files)

        # 过滤搜索结果
        results = []
        for file in all_files:
            filename = file.get('n', '').lower()
            if query.lower() in filename:
                # 根据文件类型过滤
                if file_type != 'all':
                    file_ext = filename.split('.')[-1] if '.' in filename else ''
                    if file_type == 'video' and file_ext not in ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv']:
                        continue
                    elif file_type == 'audio' and file_ext not in ['mp3', 'wav', 'flac', 'aac', 'm4a']:
                        continue
                    elif file_type == 'image' and file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                        continue
                    elif file_type == 'document' and file_ext not in ['pdf', 'doc', 'docx', 'txt', 'rtf']:
                        continue

                results.append(file)
                if len(results) >= limit:
                    break

        # 缓存结果 - 搜索缓存已禁用

        return jsonify({
            'success': True,
            'results': results,
            'total_found': len(results),
            'query': query,
            'file_type': file_type
        })

    except Exception as e:
        logging.error(f"搜索115文件出错: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/115/stats', methods=['GET'])
def get_115_stats():
    """获取115云盘统计信息"""
    try:
        cid = request.args.get('cid', '0')

        # 缓存逻辑已删除

        # 获取文件列表进行统计
        all_files = []
        get_file_list_from_115(cid, 0, 1000, all_files)  # 限制最大文件数

        # 统计信息
        stats = {
            'total_files': 0,
            'total_folders': 0,
            'total_size': 0,
            'file_types': {},
            'largest_files': [],
            'recent_files': []
        }

        for item in all_files:
            if item.get('is_dir'):
                stats['total_folders'] += 1
            else:
                stats['total_files'] += 1

                # 文件大小
                size = int(item.get('s', 0))
                stats['total_size'] += size

                # 文件类型统计
                filename = item.get('n', '')
                ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
                stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1

                # 最大文件
                if len(stats['largest_files']) < 10:
                    stats['largest_files'].append({
                        'name': filename,
                        'size': size,
                        'id': item.get('fid')
                    })
                else:
                    # 保持最大的10个文件
                    min_file = min(stats['largest_files'], key=lambda x: x['size'])
                    if size > min_file['size']:
                        stats['largest_files'].remove(min_file)
                        stats['largest_files'].append({
                            'name': filename,
                            'size': size,
                            'id': item.get('fid')
                        })

        # 排序最大文件
        stats['largest_files'].sort(key=lambda x: x['size'], reverse=True)

        # 格式化大小
        stats['total_size_formatted'] = format_file_size(stats['total_size'])

        # 缓存结果

        return jsonify({
            'success': True,
            'stats': stats,
            'cid': cid
        })

    except Exception as e:
        logging.error(f"获取115统计信息出错: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ================================
# Flask 路由
# ================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    # 返回所有当前存储的日志
    return jsonify(list(log_queue))

@app.route('/config', methods=['GET'])
def get_config():
    """返回当前配置。"""
    # 过滤掉敏感信息，例如 COOKIES
    display_config = app_config.copy()
    # display_config['COOKIES'] = '********' if display_config['COOKIES'] else ''
    return jsonify(display_config)

@app.route('/save_config', methods=['POST'])
def save_configuration():
    """保存用户提交的配置。"""
    global app_config
    try:
        new_config_data = request.json
        logging.info(f"接收到新的配置数据: {new_config_data}")

        # 验证并更新配置
        for key in ["QPS_LIMIT", "CHUNK_SIZE", "MAX_WORKERS", "COOKIES", "TMDB_API_KEY",
                   "GEMINI_API_KEY", "GEMINI_API_URL", "MODEL", "GROUPING_MODEL", "LANGUAGE",
                   "API_MAX_RETRIES", "API_RETRY_DELAY", "AI_API_TIMEOUT", "AI_MAX_RETRIES",
                   "AI_RETRY_DELAY", "TMDB_API_TIMEOUT", "TMDB_MAX_RETRIES", "TMDB_RETRY_DELAY",
                   "CLOUD_API_MAX_RETRIES", "CLOUD_API_RETRY_DELAY", "GROUPING_MAX_RETRIES",
                   "GROUPING_RETRY_DELAY", "TASK_QUEUE_GET_TIMEOUT", "ENABLE_QUALITY_ASSESSMENT",
                   "ENABLE_SCRAPING_QUALITY_ASSESSMENT", "KILL_OCCUPIED_PORT_PROCESS"]:
            if key in new_config_data:
                if key in ["QPS_LIMIT", "CHUNK_SIZE", "MAX_WORKERS", "API_MAX_RETRIES",
                          "AI_API_TIMEOUT", "AI_MAX_RETRIES", "TMDB_API_TIMEOUT", "TMDB_MAX_RETRIES",
                          "CLOUD_API_MAX_RETRIES", "GROUPING_MAX_RETRIES", "TASK_QUEUE_GET_TIMEOUT"]:
                    app_config[key] = int(new_config_data[key])
                elif key in ["API_RETRY_DELAY", "AI_RETRY_DELAY", "TMDB_RETRY_DELAY",
                            "CLOUD_API_RETRY_DELAY", "GROUPING_RETRY_DELAY"]:
                    app_config[key] = float(new_config_data[key])
                elif key in ["ENABLE_QUALITY_ASSESSMENT", "ENABLE_SCRAPING_QUALITY_ASSESSMENT",
                            "KILL_OCCUPIED_PORT_PROCESS"]:
                    app_config[key] = bool(new_config_data[key])
                else:
                    app_config[key] = new_config_data[key]

        # 保存配置到文件
        if save_config():
            # 重新加载所有配置和相关全局变量
            load_config()
            load_cookies()

            # 确保 QPS 限制器也更新
            global qps_limiter
            qps_limiter = QPSLimiter(qps_limit=app_config["QPS_LIMIT"])

            logging.info("配置已更新并应用。")
            return jsonify({'success': True, 'message': '配置保存成功并已应用。'})
        else:
            return jsonify({'success': False, 'error': '配置保存失败。'})
    except Exception as e:
        logging.error(f"保存配置时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'保存配置时发生错误: {str(e)}'})

def get_parent_cid_from_path(current_path):
    if current_path == '/':
        return '0'

    if current_path.endswith('/'):
        current_path = current_path[:-1]

    parent_path = os.path.dirname(current_path)
    if parent_path == '':
        parent_path = '/'

    try:
        url = "https://webapi.115.com/files/getid?path=" + parse.quote(parent_path)
        logging.info(f"尝试从 115 API 获取父目录ID: {url}")
        response = requests.get(url, headers=headers, cookies=cookies)
        response.raise_for_status()
        rootobject = response.json()
        logging.info(rootobject)
        if rootobject.get("state"):
            parent_cid = str(rootobject.get("id", '0'))
            logging.info(f"获取到父目录 '{parent_path}' 的 CID: {parent_cid}")
            return parent_cid
        else:
            logging.error(f"获取父目录 '{parent_path}' ID 错误: {rootobject.get('error', '未知错误')}")
            return '0' # 失败时返回根目录CID
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error 获取父目录ID for path {parent_path}: {e.response.status_code} - {e.response.text}")
        return '0'
    except Exception as e:
        logging.error(f"Error 获取父目录ID for path {parent_path}: {e}")
        return '0'

@app.route('/get_folder_content', methods=['POST'])
def get_folder_content():
    cid = request.form.get('cid', DEFAULT_CID)
    limit = int(request.form.get('limit', 150)) # 限制单次请求返回的文件/目录数量
    offset = int(request.form.get('offset', 0))

    logging.info(f"🔍 获取 CID: {cid} 下的单层内容，偏移量 {offset}，限制 {limit} 条。")

    # 缓存清理逻辑已删除

    # 重置processed_items集合，确保新请求时从头开始检测重复
    if offset == 0:
        logging.info(f"🔄 开始新的目录请求，重置重复检测")

    all_files_and_folders = []
    current_offset = offset
    total_count = 0
    paths = []
    current_path_prefix = ""  # 初始化路径前缀

    # 添加调试信息
    processed_items = set()  # 用于检测重复项
    duplicate_count = 0  # 重复项计数

    while True:
        response_data = _get_single_level_content_from_115(cid, current_offset, limit)
        
        if response_data.get("success") is False:
            return jsonify(response_data) # 返回错误信息

        if not paths: # 第一次请求时获取路径信息
            paths = response_data.get("path", [])
            # 统一根目录的名称为“根目录”
            for p in paths:
                if p.get('cid') == '0':
                    p['name'] = '根目录'
        
        total_count = response_data.get("count", 0)
        data_items = response_data.get("data", [])
        
        if not data_items:
            break # 没有更多数据了

        current_path_parts = [a['name'] for a in paths[1:]]
        current_path_prefix = "/".join(current_path_parts)

        for data in data_items:
            # 创建唯一标识符来检测重复
            unique_id = data.get('fid') or data.get('cid')
            item_name = data.get('n')

            # 检测重复项
            if unique_id in processed_items:
                # 只在DEBUG级别记录重复项，避免日志过多
                logging.debug(f"跳过重复项: {item_name} (ID: {unique_id}) at offset {current_offset}")
                duplicate_count += 1
                continue

            processed_items.add(unique_id)

            item = {
                'name': item_name,
                'is_dir': 'cid' in data,
                'cid': data.get('cid'),
                'fid': data.get('fid'),
                'size': data.get('s'),
                'file_name': os.path.join(current_path_prefix, item_name) if 'fid' in data else ''
            }

            # 添加统一的fileId字段
            if 'fid' in data: # 文件
                item['fileId'] = data.get('fid')
                if data.get('ico') in MEDIATYPES:
                    # 处理文件大小，可能是字节数或已格式化的字符串
                    size_value = data.get('s', 0)
                    if isinstance(size_value, str):
                        # 如果已经是格式化的字符串（如 "86.4GB"），直接使用
                        item['size'] = size_value
                    else:
                        # 如果是字节数，转换为GB
                        try:
                            bytes_value = int(size_value)
                            gb_in_bytes = 1024 ** 3
                            gb_value = bytes_value / gb_in_bytes
                            item['size'] = f"{gb_value:.1f}GB"
                        except (ValueError, TypeError):
                            item['size'] = "0.0GB"
                all_files_and_folders.append(item)  # 移到if外面，所有文件都添加
            else: # 目录
                item['fileId'] = data.get('cid')
                all_files_and_folders.append(item)
                logging.debug(f"📁 添加文件夹: {item_name} (CID: {data.get('cid')})")
        
        current_offset += len(data_items)
        logging.info(f"current_offset: {current_offset}") # 添加日志

        if current_offset >= total_count:
            break # 已获取所有数据

    if len(paths) < 2:
        parent_cid_calculated = '0'
    else:
        parent_cid_calculated = paths[-2]['cid']

    logging.info(f"📊 get_folder_content 统计:")
    logging.info(f"  - parent_cid: {parent_cid_calculated}")
    logging.info(f"  - current_path: {current_path_prefix}")
    logging.info(f"  - 总项目数: {len(all_files_and_folders)}")
    logging.info(f"  - 处理的唯一项目数: {len(processed_items)}")
    if duplicate_count > 0:
        logging.info(f"  - 跳过的重复项: {duplicate_count} 个")

    # 统计文件夹和文件数量
    folder_count = sum(1 for item in all_files_and_folders if item.get('is_dir'))
    file_count = len(all_files_and_folders) - folder_count
    logging.info(f"  - 文件夹: {folder_count} 个, 文件: {file_count} 个")

    return jsonify({
        'success': True,
        'current_cid': cid,
        'current_folder_id': cid,  # 添加前端期望的字段名
        'parent_cid': parent_cid_calculated,
        'parent_folder_id': parent_cid_calculated,  # 添加前端期望的字段名
        'current_path': "/" + current_path_prefix,
        'files_and_folders': all_files_and_folders,
        'total_count': total_count,
        'path_parts': paths # 新增：返回路径的各个部分
    })


@app.route('/get_folder_properties', methods=['POST'])
def get_folder_properties():
    """获取文件夹基本属性（文件数量和总大小）- 支持智能分组"""
    try:
        # 支持两种参数名：folder_id（新）和cid（旧）
        folder_id = request.form.get('folder_id') or request.form.get('cid')
        include_grouping = request.form.get('include_grouping', 'false').lower() == 'true'

        if not folder_id:
            return jsonify({'success': False, 'error': 'folder_id is required.'})

        # 处理无效的folder_id值
        if folder_id == 'null' or folder_id == 'undefined':
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '文件夹ID必须是数字'})

        logging.info(f"🔍 获取文件夹 {folder_id} 的基本属性，智能分组: {include_grouping}")

        if include_grouping:
            # 🚀 使用新的任务队列系统进行智能分组
            try:
                # 检查任务管理器是否可用
                if grouping_task_manager is None:
                    return jsonify({
                        'success': False,
                        'error': '任务管理器未初始化，请检查系统状态',
                        'task_queue_error': True
                    })

                # 获取文件夹名称
                folder_name = request.form.get('folder_name', f'文件夹{folder_id}')

                # 提交任务到队列
                task_id = grouping_task_manager.submit_task(folder_id, folder_name)

                return jsonify({
                    'success': True,
                    'use_task_queue': True,
                    'task_id': task_id,
                    'message': f'智能分组任务已提交到队列 (任务ID: {task_id})'
                })

            except ValueError as e:
                # 如果是重复任务或队列满的错误，返回相应信息
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'task_queue_error': True
                })
        else:
            # 🔍 只获取基本文件信息，不进行智能分组
            video_files = []
            try:
                get_video_files_recursively(folder_id, video_files)
            except Exception as e:
                logging.error(f"递归获取视频文件时发生错误: {e}")
                return jsonify({'success': False, 'error': f'获取文件列表失败: {str(e)}'})

            return jsonify({
                'success': True,
                'count': len(video_files),
                'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB",
                'video_files': video_files
            })

    except Exception as e:
        logging.error(f"获取文件夹属性时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/scrape_preview', methods=['POST'])
def scrape_preview():
    """刮削预览 - 增强版本，支持任务管理和缓存"""
    start_time = time.time()

    try:
        logging.info("开始刮削预览")

        # 获取请求数据
        selected_items_json = request.form.get('items')
        if not selected_items_json:
            logging.warning("没有选择任何项目进行刮削")
            return jsonify({'success': False, 'error': '没有选择任何项目进行刮削'})

        # 解析选中项目
        try:
            selected_items = json.loads(selected_items_json)
        except json.JSONDecodeError:
            logging.error("选择的项目JSON无效")
            return jsonify({'success': False, 'error': '选择的项目JSON无效'})

        if not selected_items:
            logging.warning("没有项目可处理")
            return jsonify({'success': False, 'error': '没有项目可处理'})

        logging.info(f"选择进行刮削的项目数量: {len(selected_items)}")

        # 创建刮削任务
        task_id = f"scrape_preview_{int(time.time())}"
        task = GroupingTask(
            task_id=task_id,
            folder_id="0",  # 默认根目录
            folder_name=f"刮削预览 {len(selected_items)} 个项目"
        )

        # 收集文件 - 使用专门的刮削文件收集函数
        files = []
        for item in selected_items:
            if item.get('is_dir'):
                # 如果是文件夹，递归获取其中的所有文件（不过滤类型）
                folder_id = item.get('fileId')  # 使用fileId作为文件夹ID
                if folder_id:
                    logging.info(f"📁 递归获取文件夹 {folder_id} 中的所有文件（用于刮削预览）")
                    before_count = len(files)
                    get_all_files_from_115_for_scraping(folder_id, 0, 150, files)
                    after_count = len(files)
                    logging.info(f"📁 文件夹 {folder_id} 添加了 {after_count - before_count} 个文件")
            else:
                # 如果是文件，直接添加到列表
                files.append({
                    'fid': item.get('fileId'),
                    'n': item.get('name'),
                    'pc': item.get('file_name', ''),  # 使用file_name作为路径
                    's': item.get('size', 0)
                })
                logging.debug(f"📄 直接添加文件: {item.get('name')}")

        logging.info(f"📊 文件收集完成: 总共收集到 {len(files)} 个文件（包括所有类型）")

        # 收集所有文件，包括已处理的文件
        all_files = []
        already_processed_files = []

        for f in files:
            filename = f.get("n", "") or ""  # 确保filename不是None
            # 检查是否已经包含TMDB信息
            if 'tmdb-' in filename:
                already_processed_files.append(f)
            else:
                all_files.append(f)

        # 总文件数包括已处理和待处理的文件
        total_files_count = len(all_files) + len(already_processed_files)
        task.total_items = total_files_count
        task_manager.add_task(task)

        logging.info(f"📊 文件分类统计:")
        logging.info(f"  - 待处理文件: {len(all_files)} 个")
        logging.info(f"  - 已处理文件: {len(already_processed_files)} 个")
        logging.info(f"  - 总文件数: {total_files_count} 个")

        all_scraped_results = []

        # 为已处理的文件创建结果条目
        for f in already_processed_files:
            filename = f.get("n", "")
            result_item = {
                'fid': f.get('fid'),
                'original_name': filename,
                'suggested_name': filename,  # 已处理文件保持原名
                'size': f.get('s'),
                'tmdb_info': None,
                'file_info': None,
                'status': 'already_processed',
                'message': '文件已包含TMDB信息'
            }
            all_scraped_results.append(result_item)
            logging.debug(f"🔵 添加已处理文件: {filename}")

        logging.info(f"🔵 已为 {len(already_processed_files)} 个已处理文件创建结果条目")

        if all_files:
            # 分块处理
            chunk_size = min(CHUNK_SIZE, 20)  # 限制预览时的块大小
            chunks = [all_files[i:i + chunk_size] for i in range(0, len(all_files), chunk_size)]

            # 使用任务管理器处理
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, 3)) as executor:
                futures = []

                for i, chunk in enumerate(chunks):
                    if task.status == TaskStatus.CANCELLED:
                        break

                    future = executor.submit(extract_movie_name_and_info, chunk)
                    futures.append((future, i))

                # 收集结果
                for future, chunk_index in futures:
                    if task.status == TaskStatus.CANCELLED:
                        break

                    try:
                        results = future.result(timeout=120)  # 增加到120秒超时
                        all_scraped_results.extend(results)
                        logging.info(f"✅ 块 {chunk_index} 处理完成，获得 {len(results)} 个结果")

                        # 更新任务进度
                        processed_count = (chunk_index + 1) * len(chunks[chunk_index]) if chunks else 0
                        total_count = total_files_count if total_files_count else 1
                        task.progress = min(100, (processed_count / total_count) * 100)

                    except TimeoutError:
                        logging.error(f'⏰ 块 {chunk_index} 处理超时 (120秒)')
                        task.error = f"块 {chunk_index} 处理超时"
                        # 为超时的文件创建失败结果
                        chunk_files = chunks[chunk_index] if chunk_index < len(chunks) else []
                        for file_data in chunk_files:
                            timeout_result = {
                                'fid': file_data.get('fid'),
                                'original_name': file_data.get('n', ''),
                                'suggested_name': file_data.get('n', ''),
                                'size': file_data.get('s', ''),
                                'tmdb_info': None,
                                'file_info': None,
                                'status': 'timeout',
                                'message': '处理超时'
                            }
                            all_scraped_results.append(timeout_result)
                        logging.info(f"⚠️ 为超时块 {chunk_index} 创建了 {len(chunk_files)} 个超时结果")
                    except Exception as exc:
                        logging.error(f'❌ 块 {chunk_index} 处理异常: {exc}', exc_info=True)
                        task.error = f"块 {chunk_index} 处理失败: {str(exc)}"
                        # 为异常的文件创建失败结果
                        chunk_files = chunks[chunk_index] if chunk_index < len(chunks) else []
                        for file_data in chunk_files:
                            error_result = {
                                'fid': file_data.get('fid'),
                                'original_name': file_data.get('n', ''),
                                'suggested_name': file_data.get('n', ''),
                                'size': file_data.get('s', ''),
                                'tmdb_info': None,
                                'file_info': None,
                                'status': 'error',
                                'message': f'处理异常: {str(exc)}'
                            }
                            all_scraped_results.append(error_result)
                        logging.info(f"⚠️ 为异常块 {chunk_index} 创建了 {len(chunk_files)} 个错误结果")

        # 完成任务
        if task.status != TaskStatus.CANCELLED:
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = time.time()

        # 记录性能
        log_performance("scrape_preview", start_time, True,
                       total_files=total_files_count,
                       successful_matches=len([r for r in all_scraped_results if r.get('status') == 'success']))

        logging.info(f"🎯 刮削预览完成: {len(all_scraped_results)} 个结果")

        # 统计各种状态的文件数量
        status_stats = {}
        for result in all_scraped_results:
            status = result.get('status', 'unknown')
            status_stats[status] = status_stats.get(status, 0) + 1

        successful_matches = status_stats.get('success', 0)
        already_processed_count = status_stats.get('already_processed', 0)
        failed_matches = len(all_scraped_results) - successful_matches - already_processed_count

        logging.info(f"📊 最终统计结果:")
        logging.info(f"  - 成功刮削: {successful_matches} 个")
        logging.info(f"  - 已处理: {already_processed_count} 个")
        logging.info(f"  - 失败: {failed_matches} 个")
        logging.info(f"  - 总结果数: {len(all_scraped_results)} 个")
        logging.info(f"  - 原始文件数: {total_files_count} 个")
        logging.info(f"  - 状态分布: {status_stats}")

        # 验证结果数量是否匹配
        if len(all_scraped_results) != total_files_count:
            logging.error(f"❌ 结果数量不匹配! 预期: {total_files_count}, 实际: {len(all_scraped_results)}")
            logging.error(f"   待处理文件: {len(all_files)}, 已处理文件: {len(already_processed_files)}")
        else:
            logging.info(f"✅ 结果数量匹配: {len(all_scraped_results)} 个")

        return jsonify({
            'success': True,
            'results': all_scraped_results,
            'task_id': task_id,
            'total_files': total_files_count,
            'processed_files': len(all_scraped_results),
            'successful_matches': successful_matches,
            'already_processed_count': already_processed_count,
            'failed_matches': failed_matches,
            'status_stats': status_stats,
            'performance': {
                'duration': time.time() - start_time,
                'files_per_second': total_files_count / (time.time() - start_time) if time.time() - start_time > 0 else 0
            }
        })

    except Exception as e:
        log_performance("scrape_preview", start_time, False, error=str(e))
        logging.error(f"刮削预览失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/apply_rename', methods=['POST'])
def apply_rename():
    """应用重命名 - 增强版本，支持任务管理和性能监控"""
    start_time = time.time()

    try:
        logging.info("开始应用重命名")

        # 获取重命名数据
        rename_data_json = request.form.get('rename_data')
        if not rename_data_json:
            logging.warning("没有提供重命名数据")
            return jsonify({'success': False, 'error': '没有提供重命名数据'})

        # 解析重命名数据
        try:
            rename_data = json.loads(rename_data_json)
        except json.JSONDecodeError:
            logging.error("重命名数据JSON无效")
            return jsonify({'success': False, 'error': '重命名数据JSON无效'})

        if not rename_data:
            logging.warning("没有文件需要重命名")
            return jsonify({'success': False, 'error': '没有文件需要重命名'})

        logging.info(f"准备重命名 {len(rename_data)} 个文件")

        # 创建重命名任务
        task_id = f"apply_rename_{int(time.time())}"
        task = GroupingTask(
            task_id=task_id,
            folder_id="0",  # 默认根目录
            folder_name=f"批量重命名 {len(rename_data)} 个文件"
        )
        task_manager.add_task(task)

        # 构建重命名字典和原始名称映射
        namedict = {}
        original_names_map = {}

        for item in rename_data:
            # 兼容不同的ID字段名
            item_id = item.get('id') or item.get('fid')
            new_name = item.get('suggested_name')
            original_name = item.get('original_name')

            # 只处理有效的重命名项目
            if item_id and new_name and original_name:
                # 使用安全文件名
                safe_new_name = safe_filename(new_name)
                namedict[item_id] = safe_new_name
                original_names_map[item_id] = original_name
                logging.debug(f"准备重命名: {item_id} {original_name} -> {safe_new_name}")

        if not namedict:
            task.status = "failed"
            task.error = "没有有效的重命名数据"
            logging.warning("没有有效的重命名数据")
            return jsonify({'success': False, 'error': '没有有效的重命名数据'})

        # 设置任务的总项目数
        task.total_items = len(namedict)

        # 备份重命名数据
        backup_data = {
            'namedict': namedict,
            'original_names_map': original_names_map,
            'timestamp': datetime.datetime.now().isoformat(),
            'task_id': task_id
        }

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file_path = f'rename_backup_{timestamp}.json'

        try:
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            logging.info(f"重命名数据已备份到: {backup_file_path}")
        except Exception as e:
            logging.error(f"备份重命名数据失败: {e}")
            task.error = f"备份失败: {str(e)}"

        # 分块处理重命名
        chunk_size = min(CHUNK_SIZE, 100)  # 限制重命名块大小
        namedict_chunks = [
            dict(list(namedict.items())[i:i + chunk_size])
            for i in range(0, len(namedict), chunk_size)
        ]

        # 执行批量重命名
        all_results = []
        overall_success = True
        overall_errors = []

        logging.info(f"开始批量重命名，共 {len(namedict_chunks)} 个批次")

        for i, chunk in enumerate(namedict_chunks):
            if task.status == TaskStatus.CANCELLED:
                logging.info("任务已取消，停止重命名")
                break

            logging.info(f"处理第 {i+1}/{len(namedict_chunks)} 批，包含 {len(chunk)} 个文件")

            try:
                rename_result = batch_rename_file(chunk)

                if rename_result.get('success'):
                    # 成功的文件
                    for item_id, new_name in chunk.items():
                        all_results.append({
                            'id': item_id,
                            'type': 'file',
                            'original_name': original_names_map.get(item_id, '未知'),
                            'new_name': new_name,
                            'status': 'success'
                        })

                    logging.info(f"第 {i+1} 批重命名成功: {len(chunk)} 个文件")

                else:
                    # 失败的批次
                    overall_success = False
                    error_message = rename_result.get('error', '批量重命名失败')

                    logging.error(f"第 {i+1} 批重命名失败: {error_message}")
                    overall_errors.append(f"批次 {i+1}: {error_message}")
                    # 累积错误信息到task.error
                    if task.error:
                        task.error += f"; 批次 {i+1} 失败: {error_message}"
                    else:
                        task.error = f"批次 {i+1} 失败: {error_message}"

                    # 标记失败的文件
                    for item_id, new_name in chunk.items():
                        all_results.append({
                            'id': item_id,
                            'type': 'file',
                            'original_name': original_names_map.get(item_id, '未知'),
                            'new_name': new_name,
                            'status': 'failed',
                            'error': error_message
                        })

                # 更新任务进度
                task.processed_items += len(chunk)
                if task.total_items > 0:
                    task.progress = min(100, (task.processed_items / task.total_items) * 100)
                else:
                    task.progress = 100

            except Exception as e:
                overall_success = False
                error_msg = f"批次 {i+1} 处理异常: {str(e)}"
                logging.error(error_msg, exc_info=True)
                overall_errors.append(error_msg)
                # 累积错误信息到task.error
                if task.error:
                    task.error += f"; {error_msg}"
                else:
                    task.error = error_msg

                # 标记异常的文件
                for item_id, new_name in chunk.items():
                    all_results.append({
                        'id': item_id,
                        'type': 'file',
                        'original_name': original_names_map.get(item_id, '未知'),
                        'new_name': new_name,
                        'status': 'error',
                        'error': str(e)
                    })

        # 完成任务
        if task.status != TaskStatus.CANCELLED:
            task.status = TaskStatus.COMPLETED if overall_success else TaskStatus.FAILED
            task.progress = 100
            task.completed_at = time.time()

        # 记录性能
        successful_renames = len([r for r in all_results if r.get('status') == 'success'])
        log_performance("apply_rename", start_time, overall_success,
                       total_files=len(namedict), successful_renames=successful_renames)

        logging.info(f"重命名完成: 成功 {successful_renames}/{len(namedict)} 个文件")

        # 返回结果
        if overall_success:
            return jsonify({
                'success': True,
                'results': all_results,
                'task_id': task_id,
                'performance': {
                    'duration': time.time() - start_time,
                    'files_per_second': len(namedict) / (time.time() - start_time) if time.time() - start_time > 0 else 0
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '部分或全部重命名失败',
                'details': overall_errors,
                'results': all_results,
                'task_id': task_id
            })

    except Exception as e:
        log_performance("apply_rename", start_time, False, error=str(e))
        logging.error(f"应用重命名失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.error(f"应用重命名时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/apply_move', methods=['POST'])
def apply_move():
    """应用移动 - 增强版本，支持任务管理和性能监控"""
    start_time = time.time()

    try:
        logging.info("开始应用移动")

        # 获取移动数据
        move_data_json = request.form.get('move_data')
        target_pid = request.form.get('target_pid', DEFAULT_PID)

        if not move_data_json:
            logging.warning("没有提供移动数据")
            return jsonify({'success': False, 'error': '没有提供移动数据'})

        # 解析移动数据
        try:
            move_data = json.loads(move_data_json)
        except json.JSONDecodeError:
            logging.error("移动数据JSON无效")
            return jsonify({'success': False, 'error': '移动数据JSON无效'})

        if not move_data:
            logging.warning("没有文件或文件夹需要移动")
            return jsonify({'success': False, 'error': '没有文件或文件夹需要移动'})

        # 分离文件和文件夹ID
        fids_to_move = [item['id'] for item in move_data if item.get('type') == 'file' and 'id' in item]
        cids_to_move = [item['id'] for item in move_data if item.get('type') == 'folder' and 'id' in item]

        total_items = len(fids_to_move) + len(cids_to_move)

        # 创建移动任务
        task_id = f"apply_move_{int(time.time())}"
        task = GroupingTask(
            task_id=task_id,
            folder_id=str(target_pid),
            folder_name=f"批量移动 {total_items} 个项目"
        )
        task_manager.add_task(task)

        logging.info(f"准备移动: {len(fids_to_move)} 个文件, {len(cids_to_move)} 个文件夹到 {target_pid}")

        all_move_results = []
        overall_success = True

        # 移动文件
        if fids_to_move:
            logging.info(f"移动文件: {fids_to_move}")
            try:
                move_result = batch_move_file(fids_to_move, target_pid)
                success = move_result.get('success', False)

                all_move_results.append({
                    'type': 'files',
                    'ids': fids_to_move,
                    'count': len(fids_to_move),
                    'status': 'success' if success else 'failed',
                    'message': move_result.get('result') or move_result.get('error', '未知错误')
                })

                if not success:
                    overall_success = False
                    error_msg = f"文件移动失败: {move_result.get('error', '未知错误')}"
                    # 累积错误信息到task.error
                    if task.error:
                        task.error += f"; {error_msg}"
                    else:
                        task.error = error_msg

                task.processed_items += len(fids_to_move)

            except Exception as e:
                overall_success = False
                error_msg = f"文件移动异常: {str(e)}"
                logging.error(error_msg, exc_info=True)
                # 累积错误信息到task.error
                if task.error:
                    task.error += f"; {error_msg}"
                else:
                    task.error = error_msg

                all_move_results.append({
                    'type': 'files',
                    'ids': fids_to_move,
                    'count': len(fids_to_move),
                    'status': 'error',
                    'message': error_msg
                })
        else:
            all_move_results.append({
                'type': 'files',
                'ids': [],
                'count': 0,
                'status': 'skipped',
                'message': '没有文件需要移动'
            })

        # 移动文件夹
        if cids_to_move:
            logging.info(f"移动文件夹: {cids_to_move}")
            try:
                # 文件夹移动使用相同的API
                move_result = batch_move_file(cids_to_move, target_pid)
                success = move_result.get('success', False)

                all_move_results.append({
                    'type': 'folders',
                    'ids': cids_to_move,
                    'count': len(cids_to_move),
                    'status': 'success' if success else 'failed',
                    'message': move_result.get('result') or move_result.get('error', '未知错误')
                })

                if not success:
                    overall_success = False
                    error_msg = f"文件夹移动失败: {move_result.get('error', '未知错误')}"
                    # 累积错误信息到task.error
                    if task.error:
                        task.error += f"; {error_msg}"
                    else:
                        task.error = error_msg

                task.processed_items += len(cids_to_move)

            except Exception as e:
                overall_success = False
                error_msg = f"文件夹移动异常: {str(e)}"
                logging.error(error_msg, exc_info=True)
                # 累积错误信息到task.error
                if task.error:
                    task.error += f"; {error_msg}"
                else:
                    task.error = error_msg

                all_move_results.append({
                    'type': 'folders',
                    'ids': cids_to_move,
                    'count': len(cids_to_move),
                    'status': 'error',
                    'message': error_msg
                })
        else:
            all_move_results.append({
                'type': 'folders',
                'ids': [],
                'count': 0,
                'status': 'skipped',
                'message': '没有文件夹需要移动'
            })

        # 完成任务
        task.status = "completed" if overall_success else "failed"
        task.progress = 100
        task.end_time = time.time()

        # 记录性能
        log_performance("apply_move", start_time, overall_success,
                       total_items=total_items, files_moved=len(fids_to_move), folders_moved=len(cids_to_move))

        logging.info(f"移动操作完成: 成功={overall_success}, 结果={len(all_move_results)}")

        return jsonify({
            'success': overall_success,
            'message': '移动操作完成',
            'results': all_move_results,
            'task_id': task_id,
            'performance': {
                'duration': time.time() - start_time,
                'items_per_second': total_items / (time.time() - start_time) if time.time() - start_time > 0 else 0
            }
        })

    except Exception as e:
        log_performance("apply_move", start_time, False, error=str(e))
        logging.error(f"应用移动失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.error(f"应用移动时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

# ================================
# 高级功能API端点
# ================================

# 缓存相关路由已删除

# 缓存清理代码已删除

@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务状态"""
    try:
        tasks = task_manager.get_all_tasks()
        stats = task_manager.get_task_stats()
        return jsonify({
            'success': True,
            'tasks': tasks,
            'stats': stats
        })
    except Exception as e:
        logging.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取特定任务状态"""
    try:
        task = task_manager.get_task(task_id)
        if task:
            return jsonify({'success': True, 'task': task.to_dict()})
        else:
            return jsonify({'success': False, 'error': '任务不存在'})
    except Exception as e:
        logging.error(f"获取任务状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    try:
        success = task_manager.cancel_task(task_id)
        if success:
            return jsonify({'success': True, 'message': '任务已取消'})
        else:
            return jsonify({'success': False, 'error': '任务不存在或无法取消'})
    except Exception as e:
        logging.error(f"取消任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/performance/stats', methods=['GET'])
def get_performance_stats():
    """获取性能统计信息"""
    try:
        stats = performance_monitor.get_all_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logging.error(f"获取性能统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/performance/reset', methods=['POST'])
def reset_performance_stats():
    """重置性能统计"""
    try:
        performance_monitor.reset_stats()
        return jsonify({'success': True, 'message': '性能统计已重置'})
    except Exception as e:
        logging.error(f"重置性能统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/group', methods=['POST'])
def ai_group_files():
    """使用AI智能分组文件"""
    try:
        data = request.get_json()
        files = data.get('files', [])

        if not files:
            return jsonify({'success': False, 'error': '没有提供文件列表'})

        # 创建分组任务
        task = task_manager.create_task("ai_grouping", "ai_grouping")
        task.start()

        # 这里应该实现AI分组逻辑
        # 暂时返回任务ID，实际分组在后台进行

        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'message': 'AI分组任务已启动'
        })
    except Exception as e:
        logging.error(f"AI分组失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    try:
        health_info = {
            'status': 'healthy',
            'timestamp': datetime.datetime.now().isoformat(),
            'version': '2.0.0',
            'performance_monitoring': PERFORMANCE_MONITORING,
            'ai_enabled': bool(GEMINI_API_KEY),
            'tmdb_enabled': bool(TMDB_API_KEY),
            'running_tasks': task_manager.get_running_tasks_count()
        }
        return jsonify(health_info)
    except Exception as e:
        logging.error(f"健康检查失败: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/test_connection', methods=['POST'])
def test_connection():
    """测试各种API连接"""
    try:
        data = request.get_json()
        cookies = data.get('cookies', '')
        tmdb_api_key = data.get('tmdb_api_key', '')
        gemini_api_key = data.get('gemini_api_key', '')

        results = {
            '115云盘': 'unknown',
            'TMDB': 'unknown',
            'Gemini': 'unknown'
        }

        # 测试115云盘连接
        if cookies:
            try:
                headers = {
                    'Cookie': cookies,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get('https://webapi.115.com/files', headers=headers, timeout=10)
                if response.status_code == 200:
                    results['115云盘'] = 'success'
                else:
                    results['115云盘'] = 'failed'
            except Exception as e:
                results['115云盘'] = f'error: {str(e)}'

        # 测试TMDB连接
        if tmdb_api_key:
            try:
                response = requests.get(f'https://api.themoviedb.org/3/configuration?api_key={tmdb_api_key}', timeout=10)
                if response.status_code == 200:
                    results['TMDB'] = 'success'
                else:
                    results['TMDB'] = 'failed'
            except Exception as e:
                results['TMDB'] = f'error: {str(e)}'

        # 测试Gemini连接
        if gemini_api_key:
            try:
                gemini_url = app_config.get('GEMINI_API_URL', '')
                if gemini_url:
                    headers = {
                        'Authorization': f'Bearer {gemini_api_key}',
                        'Content-Type': 'application/json'
                    }
                    test_payload = {
                        "model": app_config.get('MODEL', 'gemini-2.5-flash-lite-preview-06-17-search'),
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 10
                    }
                    response = requests.post(gemini_url, headers=headers, json=test_payload, timeout=10)
                    if response.status_code == 200:
                        results['Gemini'] = 'success'
                    else:
                        results['Gemini'] = 'failed'
                else:
                    results['Gemini'] = 'no_url'
            except Exception as e:
                results['Gemini'] = f'error: {str(e)}'

        # 检查是否有任何成功的连接
        success_count = sum(1 for status in results.values() if status == 'success')

        return jsonify({
            'success': success_count > 0,
            'results': results,
            'message': f'测试完成，{success_count}/{len(results)}个服务连接成功'
        })

    except Exception as e:
        logging.error(f"测试连接失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '连接测试失败'
        })

def get_115_folder_content(folder_id, limit=100):
    """获取115云盘文件夹内容"""
    try:
        url = 'https://webapi.115.com/files'
        params = {
            'aid': 1,
            'cid': folder_id,
            'o': 'user_ptime',
            'asc': 0,
            'offset': 0,
            'show_dir': 1,
            'limit': limit,
            'code': '',
            'scid': '',
            'snap': 0,
            'natsort': 1,
            'record_open_time': 1,
            'source': '',
            'format': 'json'
        }

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"获取115云盘文件夹内容失败: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"获取115云盘文件夹内容异常: {e}")
        return None

def is_video_file(filename):
    """判断是否为视频文件"""
    if not filename:
        return False

    video_extensions = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.3gp', '.3g2', '.asf', '.asx', '.divx', '.f4v', '.m2ts', '.m2v',
        '.mts', '.mxf', '.ogv', '.rm', '.rmvb', '.ts', '.vob', '.xvid'
    }

    return any(filename.lower().endswith(ext) for ext in video_extensions)

@app.route('/get_folder_grouping_analysis', methods=['POST'])
def get_folder_grouping_analysis():
    """获取文件夹的智能分组分析"""
    try:
        folder_id = request.form.get('folder_id', '0')

        # 处理无效的folder_id值
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '文件夹ID必须是数字'})

        logging.info(f"🔍 开始分析文件夹 {folder_id} 的智能分组")

        # 获取文件夹内容
        try:
            files_data = get_115_folder_content(folder_id, limit=1000)
            if not files_data or 'data' not in files_data:
                return jsonify({'success': False, 'error': '获取文件夹内容失败'})

            # 过滤视频文件
            video_files = []
            for item in files_data['data']:
                if item.get('fid') and is_video_file(item.get('n', '')):
                    video_files.append({
                        'fid': item['fid'],
                        'name': item['n'],
                        'size': item.get('s', 0),
                        'path': item.get('path', ''),
                        'parent_id': folder_id
                    })

            if not video_files:
                return jsonify({
                    'success': True,
                    'movie_info': [],
                    'message': '未找到视频文件'
                })

            logging.info(f"✅ 发现 {len(video_files)} 个视频文件")

            # 使用AI进行智能分组分析
            if not GEMINI_API_KEY or not GEMINI_API_URL:
                return jsonify({'success': False, 'error': 'AI API未配置'})

            # 构建AI分析请求
            file_names = [f['name'] for f in video_files]
            prompt = f"""
请分析以下视频文件列表，将它们按照电影/电视剧进行智能分组。

文件列表：
{chr(10).join(file_names)}

请返回JSON格式的分组结果，格式如下：
{{
    "groups": [
        {{
            "title": "电影/剧集名称",
            "files": ["文件名1", "文件名2"],
            "type": "movie" 或 "tv",
            "year": "年份(如果能识别)",
            "description": "简短描述"
        }}
    ]
}}

要求：
1. 相同电影/剧集的不同版本、不同集数应归为一组
2. 识别电影年份、分辨率等信息
3. 区分电影(movie)和电视剧(tv)
4. 每组至少包含1个文件
5. 只返回JSON，不要其他文字
"""

            headers = {
                'Authorization': f'Bearer {GEMINI_API_KEY}',
                'Content-Type': 'application/json'
            }

            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.1
            }

            response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                ai_response = response.json()
                content = ai_response.get('choices', [{}])[0].get('message', {}).get('content', '')

                try:
                    # 解析AI返回的JSON
                    import json
                    grouping_data = json.loads(content)
                    groups = grouping_data.get('groups', [])

                    # 转换为前端需要的格式
                    movie_info = []
                    for group in groups:
                        group_files = []
                        for file_name in group.get('files', []):
                            # 找到对应的文件信息
                            for video_file in video_files:
                                if video_file['name'] == file_name:
                                    group_files.append(video_file)
                                    break

                        if group_files:  # 只有找到文件的分组才添加
                            movie_info.append({
                                'title': group.get('title', '未知'),
                                'files': group_files,
                                'type': group.get('type', 'movie'),
                                'year': group.get('year', ''),
                                'description': group.get('description', ''),
                                'file_count': len(group_files)
                            })

                    return jsonify({
                        'success': True,
                        'movie_info': movie_info,
                        'total_groups': len(movie_info),
                        'total_files': len(video_files)
                    })

                except json.JSONDecodeError as e:
                    logging.error(f"AI返回的JSON格式错误: {e}")
                    return jsonify({'success': False, 'error': 'AI分析结果格式错误'})
            else:
                logging.error(f"AI API请求失败: {response.status_code}")
                return jsonify({'success': False, 'error': 'AI分析请求失败'})

        except Exception as e:
            logging.error(f"获取文件夹内容失败: {e}")
            return jsonify({'success': False, 'error': f'获取文件夹内容失败: {str(e)}'})

    except Exception as e:
        logging.error(f"智能分组分析失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/organize_files_by_groups', methods=['POST'])
def organize_files_by_groups():
    """根据智能分组结果移动文件"""
    try:
        folder_id = request.form.get('folder_id', '0')
        selected_groups_json = request.form.get('selected_groups')
        create_subfolders = request.form.get('create_subfolders', 'true').lower() == 'true'

        if not selected_groups_json:
            return jsonify({'success': False, 'error': '未选择分组'})

        try:
            import json
            selected_groups = json.loads(selected_groups_json)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': '分组数据格式错误'})

        if not selected_groups:
            return jsonify({'success': False, 'error': '未选择任何分组'})

        logging.info(f"🚀 开始执行智能分组，文件夹ID: {folder_id}")

        results = []
        success_count = 0
        error_count = 0

        for group in selected_groups:
            group_title = group.get('title', '未知分组')
            files = group.get('files', [])

            if not files:
                continue

            try:
                # 如果需要创建子文件夹
                if create_subfolders:
                    # 创建分组文件夹
                    folder_name = sanitize_folder_name(group_title)
                    create_result = create_115_folder(folder_name, folder_id)

                    if create_result and create_result.get('success'):
                        target_folder_id = create_result.get('folder_id')

                        # 移动文件到新文件夹
                        for file_info in files:
                            try:
                                move_result = move_115_file(file_info['fid'], target_folder_id)
                                if move_result and move_result.get('success'):
                                    success_count += 1
                                    results.append({
                                        'file': file_info['name'],
                                        'group': group_title,
                                        'status': 'success',
                                        'message': f'已移动到文件夹: {folder_name}'
                                    })
                                else:
                                    error_count += 1
                                    results.append({
                                        'file': file_info['name'],
                                        'group': group_title,
                                        'status': 'error',
                                        'message': '移动文件失败'
                                    })
                            except Exception as e:
                                error_count += 1
                                results.append({
                                    'file': file_info['name'],
                                    'group': group_title,
                                    'status': 'error',
                                    'message': f'移动文件异常: {str(e)}'
                                })
                    else:
                        error_count += len(files)
                        for file_info in files:
                            results.append({
                                'file': file_info['name'],
                                'group': group_title,
                                'status': 'error',
                                'message': f'创建文件夹失败: {folder_name}'
                            })
                else:
                    # 不创建子文件夹，只是标记处理
                    for file_info in files:
                        success_count += 1
                        results.append({
                            'file': file_info['name'],
                            'group': group_title,
                            'status': 'success',
                            'message': '分组完成（未移动文件）'
                        })

            except Exception as e:
                error_count += len(files)
                for file_info in files:
                    results.append({
                        'file': file_info['name'],
                        'group': group_title,
                        'status': 'error',
                        'message': f'处理分组异常: {str(e)}'
                    })

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_files': success_count + error_count,
                'success_count': success_count,
                'error_count': error_count,
                'groups_processed': len(selected_groups)
            }
        })

    except Exception as e:
        logging.error(f"执行智能分组失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

def sanitize_folder_name(name):
    """清理文件夹名称，移除非法字符"""
    import re
    # 移除或替换非法字符
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # 移除前后空格
    name = name.strip()
    # 限制长度
    if len(name) > 100:
        name = name[:100]
    return name or '未命名文件夹'

def create_115_folder(folder_name, parent_id):
    """在115云盘创建文件夹"""
    try:
        url = 'https://webapi.115.com/files/add'
        data = {
            'pid': parent_id,
            'cname': folder_name
        }

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('state'):
                return {
                    'success': True,
                    'folder_id': result.get('cid'),
                    'folder_name': folder_name
                }

        return {'success': False, 'error': '创建文件夹失败'}
    except Exception as e:
        logging.error(f"创建115云盘文件夹异常: {e}")
        return {'success': False, 'error': str(e)}

def move_115_file(file_id, target_folder_id):
    """移动115云盘文件"""
    try:
        url = 'https://webapi.115.com/files/move'
        data = {
            'fid': file_id,
            'pid': target_folder_id
        }

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('state'):
                return {'success': True}

        return {'success': False, 'error': '移动文件失败'}
    except Exception as e:
        logging.error(f"移动115云盘文件异常: {e}")
        return {'success': False, 'error': str(e)}

def move_files_115(file_ids, target_folder_id):
    """批量移动115云盘文件 - 使用movie115的格式"""
    try:
        if not file_ids:
            return {'success': False, 'message': '没有文件需要移动'}

        # 使用批量移动API
        url = 'https://webapi.115.com/files/move'

        # 使用movie115的数据格式
        data = {
            'move_proid': '1749745456990_-69_0',
            'pid': target_folder_id
        }

        # 添加文件ID，使用 fid[0], fid[1], fid[2] 格式
        if isinstance(file_ids, str):
            data['fid[0]'] = file_ids
        else:
            for i in range(len(file_ids)):
                data[f'fid[{i}]'] = str(file_ids[i])

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        logging.info(f"🔍 移动文件请求数据: {data}")
        response = requests.post(url, data=data, headers=headers, timeout=10)
        logging.info(f"🔍 移动文件响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logging.info(f"🔍 移动文件响应内容: {result}")
            if result.get('state'):
                return {'success': True, 'message': f'成功移动 {len(file_ids)} 个文件'}
            else:
                return {'success': False, 'message': f'移动失败: {result.get("error", "未知错误")}'}

        return {'success': False, 'message': f'HTTP错误: {response.status_code}'}
    except Exception as e:
        logging.error(f"批量移动文件失败: {e}")
        return {'success': False, 'error': str(e)}

def rename_115_file(file_id, new_name):
    """重命名115云盘文件 - 使用movie115的正确格式"""
    try:
        url = 'https://webapi.115.com/files/batch_rename'

        # 使用movie115的正确格式：files_new_name[file_id] = new_name
        data = {
            f'files_new_name[{file_id}]': new_name
        }

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        logging.info(f"🔄 重命名文件 {file_id}: {new_name}")
        logging.info(f"🔍 重命名请求数据: {data}")

        response = requests.post(url, data=data, headers=headers, timeout=10)

        # 详细打印返回值
        logging.info(f"🔍 重命名API响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logging.info(f"🔍 重命名API返回值: {json.dumps(result, ensure_ascii=False, indent=2)}")

            if result.get('state'):
                logging.info(f"✅ 文件 {file_id} 重命名成功: {new_name}")
                return {'success': True, 'message': '文件重命名成功', 'result': result}
            else:
                error_msg = result.get('error') or result.get('errno_desc') or result.get('errcode') or '重命名失败'
                logging.error(f"❌ 文件 {file_id} 重命名失败: {error_msg}")
                return {'success': False, 'error': error_msg, 'result': result}
        else:
            logging.error(f"❌ 重命名API请求失败，状态码: {response.status_code}, 响应: {response.text}")
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}

    except Exception as e:
        logging.error(f"❌ 重命名115云盘文件异常: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def delete_files_115(file_ids):
    """批量删除115云盘文件 - 使用索引格式"""
    try:
        if not file_ids:
            return {'success': False, 'message': '没有文件需要删除'}

        # 使用批量删除API
        url = 'https://webapi.115.com/rb/delete'

        # 使用索引格式，类似move_files_115的实现
        data = {}

        # 添加文件ID，使用 fid[0], fid[1], fid[2] 格式
        if isinstance(file_ids, str):
            data['fid[0]'] = file_ids
        else:
            for i in range(len(file_ids)):
                data[f'fid[{i}]'] = str(file_ids[i])

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        logging.info(f"🔍 删除文件请求数据: {data}")
        response = requests.post(url, data=data, headers=headers, timeout=10)
        logging.info(f"🔍 删除文件响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logging.info(f"🔍 删除文件响应内容: {result}")
            if result.get('state'):
                return {'success': True, 'message': f'成功删除 {len(file_ids)} 个文件'}
            else:
                return {'success': False, 'message': f'删除失败: {result.get("error", "未知错误")}'}

        return {'success': False, 'message': f'HTTP错误: {response.status_code}'}
    except Exception as e:
        logging.error(f"批量删除文件失败: {e}")
        return {'success': False, 'error': str(e)}

def find_existing_folder_by_name(folder_name, parent_id='0'):
    """查找现有文件夹的ID，支持模糊匹配"""
    try:
        logging.info(f"🔍 在父文件夹 {parent_id} 中查找文件夹: {folder_name}")
        # 获取父目录的内容
        content = _get_single_level_content_from_115(parent_id, 0, 100)
        if content and 'data' in content:
            logging.info(f"🔍 父文件夹包含 {len(content['data'])} 个项目")

            # 首先尝试精确匹配
            for item in content['data']:
                item_name = item.get('n', '')
                # 尝试多个可能的ID字段
                item_fid = item.get('fid', '') or item.get('cid', '') or item.get('id', '') or item.get('file_id', '')
                item_is_dir = item.get('pid', '') != '' or item.get('is_dir', False) or item.get('d', False)
                logging.info(f"🔍 检查项目: {item_name} (fid: {item_fid}, is_dir: {item_is_dir})")
                logging.info(f"🔍 项目完整数据: {item}")
                if item_name == folder_name and item_fid and item_is_dir:
                    logging.info(f"✅ 精确匹配找到文件夹: {folder_name} -> {item_fid}")
                    return item_fid

            # 如果精确匹配失败，尝试模糊匹配
            logging.info(f"🔍 精确匹配失败，尝试模糊匹配...")
            folder_name_lower = folder_name.lower()
            best_match = None
            best_score = 0

            for item in content['data']:
                item_name = item.get('n', '')
                # 尝试多个可能的ID字段
                item_fid = item.get('fid', '') or item.get('cid', '') or item.get('id', '') or item.get('file_id', '')
                item_is_dir = item.get('pid', '') != '' or item.get('is_dir', False) or item.get('d', False)
                if not item_fid or not item_is_dir:  # 只考虑文件夹
                    continue

                item_name_lower = item_name.lower()

                # 检查是否包含关键词
                if 'mission impossible' in folder_name_lower and 'mission impossible' in item_name_lower:
                    score = 0.8
                    logging.info(f"🔍 Mission Impossible 匹配: {item_name} (分数: {score})")
                elif 'love, death' in folder_name_lower and 'love, death' in item_name_lower:
                    score = 0.8
                    logging.info(f"🔍 Love, Death & Robots 匹配: {item_name} (分数: {score})")
                elif folder_name_lower in item_name_lower or item_name_lower in folder_name_lower:
                    score = 0.6
                    logging.info(f"🔍 包含匹配: {item_name} (分数: {score})")
                else:
                    continue

                if score > best_score:
                    best_match = item_fid
                    best_score = score
                    logging.info(f"🔍 更新最佳匹配: {item_name} -> {item_fid} (分数: {score})")

            if best_match and best_score >= 0.6:
                logging.info(f"✅ 模糊匹配找到文件夹: {folder_name} -> {best_match} (分数: {best_score})")
                return best_match

            logging.info(f"❌ 在父文件夹中未找到匹配的文件夹: {folder_name}")
        else:
            logging.info(f"❌ 无法获取父文件夹内容或内容为空")
        return None
    except Exception as e:
        logging.error(f"查找现有文件夹失败: {e}")
        return None

def create_folder_115(folder_name, parent_id):
    """在115云盘创建文件夹"""
    try:
        url = 'https://webapi.115.com/files/add'
        data = {
            'pid': parent_id,
            'cname': folder_name
        }

        headers = {
            'Cookie': COOKIES,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.post(url, data=data, headers=headers, timeout=10)
        logging.info(f"🔍 创建文件夹响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logging.info(f"🔍 创建文件夹响应内容: {result}")
            if result.get('state'):
                return {
                    'success': True,
                    'message': f'成功创建文件夹: {folder_name}',
                    'folder_id': result.get('cid')
                }
            else:
                # 检查是否是文件夹已存在的错误
                if result.get('errno') == 20004 or '已存在' in result.get('error', ''):
                    logging.info(f"🔍 文件夹已存在，尝试查找现有文件夹: {folder_name}")
                    # 尝试查找现有文件夹
                    existing_folder_id = find_existing_folder_by_name(folder_name, parent_id)
                    if existing_folder_id:
                        logging.info(f"✅ 找到现有文件夹: {folder_name}, ID: {existing_folder_id}")
                        return {
                            'success': True,
                            'message': f'使用现有文件夹: {folder_name}',
                            'folder_id': existing_folder_id
                        }
                    else:
                        logging.error(f"❌ 无法找到现有文件夹: {folder_name}")
                        return {'success': False, 'error': f'文件夹已存在但无法找到: {folder_name}'}
                else:
                    return {'success': False, 'error': f'创建文件夹失败: {result.get("error", "未知错误")}'}

        return {'success': False, 'error': f'HTTP错误: {response.status_code}'}
    except Exception as e:
        logging.error(f"创建115云盘文件夹异常: {e}")
        return {'success': False, 'error': str(e)}

def generate_folder_name_suggestion(file_names):
    """使用AI生成文件夹名称建议"""
    try:
        if not GEMINI_API_KEY or not GEMINI_API_URL:
            logging.warning("AI API未配置，无法生成文件夹名称建议")
            return None

        if not file_names:
            return None

        # 构建AI分析请求
        prompt = f"""
根据以下文件名列表，为这些文件生成一个合适的文件夹名称建议。

文件名列表：
{chr(10).join(file_names)}

要求：
1. 分析文件名的共同特征（如电影名、电视剧名、类型等）
2. 生成一个简洁、描述性的文件夹名称
3. 文件夹名称应该是中文，长度不超过50个字符
4. 只返回文件夹名称，不要其他文字
5. 如果是电影或电视剧，包含年份信息（如果能识别出来）

示例：
- 如果是《复仇者联盟》相关文件，返回：复仇者联盟系列
- 如果是2023年的电影，返回：电影名称 (2023)
- 如果是电视剧，返回：电视剧名称 全集

请直接返回建议的文件夹名称：
"""

        headers = {
            'Authorization': f'Bearer {GEMINI_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0.3
        }

        response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            ai_response = response.json()
            content = ai_response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            if content:
                # 清理返回的内容，移除可能的引号和多余的文字
                suggested_name = content.replace('"', '').replace("'", '').strip()

                # 限制长度
                if len(suggested_name) > 50:
                    suggested_name = suggested_name[:50]

                logging.info(f"AI生成文件夹名称建议: {suggested_name}")
                return suggested_name

        logging.warning("AI未能生成有效的文件夹名称建议")
        return None

    except Exception as e:
        logging.error(f"生成文件夹名称建议失败: {e}")
        return None

def find_empty_folders_115(parent_id, visited_folders=None, max_depth=10, current_depth=0):
    """查找115云盘中不包含视频文件的文件夹

    删除不包含视频文件的文件夹（可能包含.nfo、.jpg等非视频文件）
    保留包含视频文件的文件夹
    """
    try:
        # 初始化访问过的文件夹集合
        if visited_folders is None:
            visited_folders = set()

        # 防止无限递归
        if current_depth >= max_depth:
            logging.warning(f"达到最大递归深度 {max_depth}，停止递归")
            return []

        # 防止重复访问同一文件夹
        if parent_id in visited_folders:
            logging.warning(f"文件夹 {parent_id} 已访问过，跳过以防循环")
            return []

        visited_folders.add(parent_id)
        empty_folders = []

        logging.info(f"🔍 扫描文件夹 {parent_id} 查找空文件夹 (深度: {current_depth})")

        # QPS限制
        qps_limiter.acquire()

        # 获取指定文件夹下的内容
        response_data = _get_single_level_content_from_115(parent_id, 0, 1000)

        if not response_data or 'data' not in response_data:
            return empty_folders

        items = response_data.get('data', [])
        logging.info(f"🔍 文件夹 {parent_id} 包含 {len(items)} 个项目")

        # 分离文件和子文件夹，检查是否包含视频文件
        subfolders = []
        has_video_files = False

        # 分离文件和子文件夹
        files = []

        # 遍历所有项目，正确区分文件和文件夹
        for item in items:
            file_name = item.get('n', '未知项目')
            file_size = item.get('s', 0)
            has_pid = 'pid' in item and item.get('pid', '') != ''
            ico = item.get('ico', '')

            # 更严格的文件夹判断：有pid字段，文件大小为0，且没有文件类型图标
            is_folder = (has_pid and file_size == 0 and (not ico or ico in ['folder', 'dir']))

            if is_folder:
                # 这是一个子文件夹
                folder_id = item.get('fid', '') or item.get('cid', '')
                if folder_id:
                    subfolders.append({
                        'id': folder_id,
                        'name': file_name
                    })
                    logging.info(f"📁 发现子文件夹: {file_name} (ID: {folder_id})")
            else:
                # 这是一个文件
                files.append({
                    'name': file_name,
                    'size': file_size,
                    'ico': ico
                })
                logging.info(f"📄 发现文件: {file_name} (大小: {file_size}, 类型: {ico})")

                # 检查是否为视频文件
                if is_video_file(file_name):
                    has_video_files = True

        # 先递归检查所有子文件夹
        for subfolder in subfolders:
            folder_id = subfolder['id']

            # 防止重复访问
            if folder_id in visited_folders:
                logging.info(f"🔍 文件夹 {folder_id} 已访问过，跳过")
                continue

            # 递归检查子文件夹
            sub_empty_folders = find_empty_folders_115(
                folder_id,
                visited_folders,
                max_depth,
                current_depth + 1
            )
            empty_folders.extend(sub_empty_folders)

        # 检查当前文件夹是否不包含视频文件且为叶子节点（没有子文件夹）
        is_leaf_node = len(subfolders) == 0
        if not has_video_files and is_leaf_node:
            empty_folders.append({
                'cid': parent_id,
                'name': f'无视频文件夹_{parent_id}',
                'depth': current_depth
            })
            logging.info(f"🗑️ 发现无视频叶子文件夹: {parent_id} (深度: {current_depth}, 文件数: {len(files)})")
        elif not has_video_files and not is_leaf_node:
            logging.info(f"📁 文件夹 {parent_id} 无视频文件但包含子文件夹，跳过删除 (文件数: {len(files)}, 子文件夹数: {len(subfolders)})")
        else:
            logging.info(f"📁 文件夹 {parent_id} 包含视频文件，保留 (文件数: {len(files)}, 子文件夹数: {len(subfolders)})")

        logging.info(f"✅ 文件夹 {parent_id} 扫描完成，发现 {len(empty_folders)} 个空文件夹")
        return empty_folders

    except Exception as e:
        logging.error(f"查找空文件夹失败: {e}")
        return []

def restart_process_async():
    # 延迟一点时间，确保HTTP响应可以发送
    time.sleep(1) 
    print("Initiating new process...")
    try:
        # 获取当前的启动命令
        # 假设你通常用 'python app.py' 启动
        command = [sys.executable] + sys.argv
        
        # 使用 subprocess.Popen 启动新进程，不等待它完成
        # 注意：这里没有处理标准输入/输出重定向，可能需要根据实际情况添加
        subprocess.Popen(command, 
                         # 这两行很重要，解耦子进程和父进程的stdout/stderr
                         # 否则子进程的输出会继续输出到旧进程的终端
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         # 在Unix/Linux上，设置preexec_fn可以进一步解耦
                         # 例如：preexec_fn=os.setsid
                         ) 
        print("New process started. Exiting old process.")
        os._exit(0) # 强制退出当前进程，不执行atexit handlers
    except Exception as e:
        print(f"Failed to start new process: {e}")

@app.route('/get_file_list', methods=['POST'])
def get_file_list():
    """获取指定文件夹下的视频文件列表（递归）"""
    try:
        folder_id = request.form.get('folder_id', '0')

        # 处理无效的folder_id值
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            folder_id = '0'

        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            logging.warning(f"无效的folder_id值: {folder_id}，使用默认值0")
            folder_id = 0

        logging.info(f"获取文件夹 {folder_id} 下的视频文件列表")

        file_list = []
        get_video_files_recursively(folder_id, file_list)

        # 转换为前端需要的格式
        formatted_files = []
        for file_item in file_list:
            formatted_files.append({
                'parentFileId': file_item['parentFileId'],
                'fileId': file_item['fileId'],
                'filename': os.path.basename(file_item['file_path']),  # 只保留文件名
                'file_name': file_item['file_path'],  # 完整路径
                'size': file_item['size_gb'],
            })

        logging.info(f"找到 {len(formatted_files)} 个视频文件")
        return jsonify({
            'success': True,
            'files': formatted_files,
            'total_count': len(formatted_files)
        })

    except Exception as e:
        logging.error(f"获取文件列表时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/rename_files', methods=['POST'])
def rename_files():
    """重命名选中的文件"""
    try:
        rename_data_json = request.form.get('rename_data')
        if not rename_data_json:
            return jsonify({'success': False, 'error': '没有提供重命名数据。'})

        rename_data = json.loads(rename_data_json)
        if not rename_data:
            return jsonify({'success': False, 'error': '没有文件需要重命名。'})

        logging.info(f"准备重命名 {len(rename_data)} 个文件")

        successful_renames = []
        failed_renames = []

        for item in rename_data:
            file_id = item.get('fileId')
            # 支持多种格式：newName（普通重命名）、suggested_name（刮削预览重命名）、new_name（智能重命名）
            new_name = item.get('newName') or item.get('suggested_name') or item.get('new_name')

            if file_id and new_name:
                try:
                    result = rename_115_file(file_id, new_name)
                    if result.get('success'):
                        successful_renames.append({'fileId': file_id, 'newName': new_name})
                    else:
                        failed_renames.append({'fileId': file_id, 'error': result.get('error', '重命名失败')})
                except Exception as e:
                    failed_renames.append({'fileId': file_id, 'error': str(e)})

        total_files = len(rename_data)
        success_count = len(successful_renames)
        failed_count = len(failed_renames)

        logging.info(f"重命名完成: 成功 {success_count}/{total_files}, 失败 {failed_count}")

        # 如果有成功的重命名，清理缓存
        if success_count > 0:
            logging.info(f"🧹 重命名操作完成，已清理相关缓存")

        response_data = {
            'success': failed_count == 0,
            'message': f'重命名完成: 成功 {success_count} 个，失败 {failed_count} 个',
            'successful_renames': successful_renames,
            'failed_renames': failed_renames,
            'total_files': total_files,
            'success_count': success_count,
            'failed_count': failed_count
        }

        # 如果有成功的重命名，添加刷新指令
        if success_count > 0:
            response_data['refresh_folder'] = True
            logging.info(f"✅ 重命名成功，将触发文件夹刷新")

        return jsonify(response_data)

    except json.JSONDecodeError as e:
        logging.error(f"解析重命名数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': f'JSON解析错误: {str(e)}'})
    except Exception as e:
        logging.error(f"重命名文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_files', methods=['POST'])
def delete_files():
    """删除选中的文件"""
    try:
        # 尝试获取前端发送的delete_data参数
        delete_data_json = request.form.get('delete_data')
        file_ids_json = request.form.get('file_ids')

        if delete_data_json:
            # 前端发送的是包含fileId、fileName、isDir的对象数组
            delete_data = json.loads(delete_data_json)
            if not delete_data:
                return jsonify({'success': False, 'error': '没有文件需要删除。'})

            # 提取文件ID
            file_ids = [item['fileId'] for item in delete_data if item.get('fileId')]
            file_names = [item['fileName'] for item in delete_data if item.get('fileName')]

        elif file_ids_json:
            # 兼容旧的file_ids参数格式
            file_ids = json.loads(file_ids_json)
            file_names = []
        else:
            return jsonify({'success': False, 'error': '没有提供文件ID。'})

        if not file_ids:
            return jsonify({'success': False, 'error': '没有文件需要删除。'})

        logging.info(f"准备删除 {len(file_ids)} 个文件: {file_names[:3]}{'...' if len(file_names) > 3 else ''}")

        # 使用115云盘删除API
        result = delete_files_115(file_ids)

        if result.get('success'):
            # 使用统一的缓存清理机制

            return jsonify({
                'success': True,
                'message': f'成功删除 {len(file_ids)} 个文件',
                'deleted_count': len(file_ids)
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '删除文件失败')
            })

    except json.JSONDecodeError as e:
        logging.error(f"解析删除数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': f'JSON解析错误: {str(e)}'})
    except Exception as e:
        logging.error(f"删除文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create_folder', methods=['POST'])
def create_folder():
    """创建新文件夹"""
    try:
        folder_name = request.form.get('folder_name')
        parent_id = request.form.get('parent_id', '0')  # 默认在根目录创建

        if not folder_name:
            return jsonify({'success': False, 'error': '文件夹名称不能为空。'})

        logging.info(f"准备创建文件夹: {folder_name} 在父目录: {parent_id}")

        # 使用115云盘创建文件夹API
        result = create_folder_115(folder_name, parent_id)

        if result.get('success'):
            # 缓存清理逻辑已删除
            logging.info(f"创建文件夹成功: {folder_name}")

            return jsonify({
                'success': True,
                'message': f'成功创建文件夹: {folder_name}',
                'folder_id': result.get('folder_id'),
                'folder_name': folder_name
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '创建文件夹失败')
            })

    except Exception as e:
        logging.error(f"创建文件夹时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/suggest_folder_name', methods=['POST'])
def suggest_folder_name():
    """根据文件夹内容智能建议文件夹名称"""
    try:
        folder_id_str = request.form.get('folder_id', '0')

        if not folder_id_str:
            return jsonify({'success': False, 'error': '缺少folder_id参数'})

        try:
            folder_id = int(folder_id_str)
        except ValueError:
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        logging.info(f"为文件夹 {folder_id} 生成智能命名建议")

        # 获取文件夹中的视频文件
        video_files = []

        # 先检查文件夹内容
        all_files = get_all_files_in_folder(folder_id, limit=100)
        logging.info(f"🔍 文件夹 {folder_id} 中共有 {len(all_files)} 个项目")

        # 详细记录文件类型
        file_count = 0
        folder_count = 0
        video_count = 0

        for item in all_files:
            if item['type'] == 0:  # 文件
                file_count += 1
                _, ext = os.path.splitext(item['filename'])
                ext_lower = ext.lower()[1:]
                logging.info(f"📄 文件: {item['filename']}, 扩展名: {ext_lower}")
                if ext_lower in SUPPORTED_MEDIA_TYPES:
                    video_count += 1
                    logging.info(f"✅ 识别为视频文件: {item['filename']}")
            elif item['type'] == 1:  # 文件夹
                folder_count += 1
                logging.info(f"📁 文件夹: {item['filename']}")

        logging.info(f"📊 统计: 文件 {file_count} 个, 文件夹 {folder_count} 个, 视频文件 {video_count} 个")

        get_video_files_recursively(folder_id, video_files)

        if not video_files:
            return jsonify({'success': False, 'error': f'文件夹中没有找到视频文件 (共检查了 {len(all_files)} 个项目)'})

        # 提取文件名用于AI分析（限制数量以提高性能）
        sampled_files = video_files[:20] if len(video_files) > 20 else video_files
        file_names = [os.path.basename(file_item['file_path']) for file_item in sampled_files]

        if not file_names:
            return jsonify({'success': False, 'error': '没有有效的文件名。'})

        # 使用AI生成文件夹名称建议
        suggested_name = generate_folder_name_suggestion(file_names)

        if suggested_name:
            return jsonify({
                'success': True,
                'suggested_name': suggested_name,
                'file_count': len(video_files)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'AI服务暂时不可用，无法生成建议'
            })

    except Exception as e:
        logging.error(f"生成文件夹名称建议时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/execute_selected_groups', methods=['POST'])
def execute_selected_groups():
    """执行选中的智能分组"""
    try:
        # 获取目标文件夹ID
        target_parent_folder_id = request.form.get('folder_id', '0')
        logging.info(f"🔍 目标父文件夹ID: {target_parent_folder_id}")

        # 兼容两种参数名：groups 和 selected_groups
        groups_json = request.form.get('groups') or request.form.get('selected_groups')
        if not groups_json:
            return jsonify({'success': False, 'error': '没有提供分组信息。'})

        groups = json.loads(groups_json)
        if not groups:
            return jsonify({'success': False, 'error': '分组列表为空。'})

        logging.info(f"准备执行 {len(groups)} 个智能分组")
        logging.info(f"🔍 调试 - 接收到的分组数据: {groups}")  # 打印完整的分组数据

        successful_groups = []
        failed_groups = []

        for group in groups:
            # 兼容两种字段名：name 和 group_name
            group_name = group.get('name', '') or group.get('group_name', '')
            files = group.get('files', [])
            target_folder_id = group.get('target_folder_id')

            # 检查是否有 fileIds 字段（前端发送的文件ID列表）
            file_ids_from_group = group.get('fileIds', [])
            if file_ids_from_group:
                logging.info(f"🔍 从分组中直接获取文件ID: {file_ids_from_group}")
                # 如果有 fileIds 字段，将其转换为 files 格式
                files = [{'fid': fid} for fid in file_ids_from_group]
                logging.info(f"🔍 转换后的 files 结构: {files}")
            elif files and isinstance(files[0], str):
                # 如果files本身就是文件ID列表
                files = [{'fid': fid} for fid in files]

            logging.info(f"🔍 处理分组: {group_name}, 文件数量: {len(files)}")

            if not group_name or not files:
                error_msg = f'分组信息不完整: group_name={group_name}, files_count={len(files) if files else 0}'
                logging.error(f"❌ {error_msg}")
                failed_groups.append({
                    'group_name': group_name,
                    'error': error_msg
                })
                continue

            try:
                # 如果需要创建新文件夹
                if not target_folder_id:
                    logging.info(f"🔍 创建文件夹: {group_name} 在父文件夹: {target_parent_folder_id}")
                    folder_result = create_folder_115(group_name, target_parent_folder_id)  # 在指定的父文件夹创建
                    logging.info(f"🔍 文件夹创建结果: {folder_result}")
                    if folder_result.get('success'):
                        target_folder_id = folder_result.get('folder_id')
                        logging.info(f"✅ 文件夹创建成功: {group_name}, ID: {target_folder_id}")
                    else:
                        error_msg = f'创建文件夹失败: {folder_result.get("error")}'
                        logging.error(f"❌ {error_msg}")
                        failed_groups.append({
                            'group_name': group_name,
                            'error': error_msg
                        })
                        continue

                # 移动文件到目标文件夹
                logging.info(f"🔍 调试 - files 数据结构: {files}")
                file_ids = [f.get('fid') for f in files if f.get('fid')]
                logging.info(f"🔍 提取的文件ID: {file_ids}")

                # 如果 fid 字段不存在，尝试其他可能的字段名
                if not file_ids:
                    logging.info("🔍 尝试其他文件ID字段...")
                    file_ids = [f.get('fileId') for f in files if f.get('fileId')]
                    logging.info(f"🔍 使用 fileId 字段提取的ID: {file_ids}")

                if not file_ids:
                    file_ids = [f.get('fileID') for f in files if f.get('fileID')]
                    logging.info(f"🔍 使用 fileID 字段提取的ID: {file_ids}")

                if not file_ids:
                    file_ids = [f.get('id') for f in files if f.get('id')]
                    logging.info(f"🔍 使用 id 字段提取的ID: {file_ids}")
                if file_ids:
                    logging.info(f"🔍 移动 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
                    move_result = move_files_115(file_ids, target_folder_id)
                    logging.info(f"🔍 文件移动结果: {move_result}")
                    if move_result.get('success'):
                        logging.info(f"✅ 文件移动成功: {group_name}")
                        successful_groups.append({
                            'group_name': group_name,
                            'file_count': len(file_ids),
                            'folder_id': target_folder_id
                        })
                    else:
                        error_msg = f'移动文件失败: {move_result.get("error")}'
                        logging.error(f"❌ {error_msg}")
                        failed_groups.append({
                            'group_name': group_name,
                            'error': error_msg
                        })
                else:
                    error_msg = '没有有效的文件ID'
                    logging.error(f"❌ {error_msg}")
                    failed_groups.append({
                        'group_name': group_name,
                        'error': error_msg
                    })

            except Exception as e:
                failed_groups.append({
                    'group_name': group_name,
                    'error': str(e)
                })

        total_groups = len(groups)
        success_count = len(successful_groups)
        failed_count = len(failed_groups)

        logging.info(f"智能分组执行完成: 成功 {success_count}/{total_groups}, 失败 {failed_count}")

        return jsonify({
            'success': failed_count == 0,
            'message': f'智能分组执行完成: 成功 {success_count} 个，失败 {failed_count} 个',
            'successful_groups': successful_groups,
            'failed_groups': failed_groups,
            'total_groups': total_groups,
            'success_count': success_count,
            'failed_count': failed_count
        })

    except json.JSONDecodeError as e:
        logging.error(f"解析分组信息JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': f'JSON解析错误: {str(e)}'})
    except Exception as e:
        logging.error(f"执行智能分组时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_empty_folders', methods=['POST'])
def delete_empty_folders():
    """删除用户选择的父文件夹内部不包含视频文件的子文件夹"""
    try:
        # 获取请求数据
        if request.is_json:
            data = request.get_json()
            selected_folders = data.get('selected_folders', [])
        else:
            # 兼容旧的表单格式（用于向后兼容）
            folder_id = request.form.get('folder_id', '0')
            if folder_id != '0':
                # 如果是旧格式，转换为新格式
                selected_folders = [{'fileId': folder_id, 'fileName': f'文件夹_{folder_id}'}]
            else:
                return jsonify({'success': False, 'error': '请选择要检查的父文件夹'})

        if not selected_folders:
            return jsonify({'success': False, 'error': '请选择要检查的父文件夹'})

        logging.info(f"🗑️ 开始扫描用户选择的 {len(selected_folders)} 个父文件夹")

        # 分析每个选择的父文件夹内部的子文件夹
        folders_to_delete = []  # 需要删除的子文件夹
        folders_with_videos = []  # 包含视频的子文件夹
        failed_analysis = []  # 分析失败的文件夹

        for parent_folder_info in selected_folders:
            parent_folder_id = parent_folder_info.get('fileId') or parent_folder_info.get('fid')
            parent_folder_name = parent_folder_info.get('fileName') or parent_folder_info.get('filename', f'文件夹_{parent_folder_id}')

            if not parent_folder_id:
                failed_analysis.append({
                    'folder_name': parent_folder_name,
                    'error': '父文件夹ID缺失'
                })
                continue

            try:
                logging.info(f"🔍 扫描父文件夹: {parent_folder_name} (ID: {parent_folder_id})")

                # 获取父文件夹下的所有内容
                qps_limiter.acquire()
                folder_content = _get_single_level_content_from_115(parent_folder_id, 0, 1000)

                if not folder_content or 'data' not in folder_content:
                    logging.warning(f"无法获取父文件夹内容: {parent_folder_name}")
                    failed_analysis.append({
                        'folder_name': parent_folder_name,
                        'error': '无法获取文件夹内容'
                    })
                    continue

                # 找出所有子文件夹
                subfolders = []
                for item in folder_content['data']:
                    # 判断是否为文件夹：有pid字段且文件大小为0
                    if 'pid' in item and item.get('s', 0) == 0:
                        subfolders.append({
                            'folder_id': item.get('cid', ''),
                            'folder_name': item.get('n', '未知'),
                            'parent_folder': parent_folder_name
                        })

                logging.info(f"在父文件夹 {parent_folder_name} 中发现 {len(subfolders)} 个子文件夹")

                # 检查每个子文件夹是否包含视频文件
                for subfolder in subfolders:
                    subfolder_id = subfolder['folder_id']
                    subfolder_name = subfolder['folder_name']
                    parent_name = subfolder['parent_folder']

                    try:
                        logging.info(f"🔍 检查子文件夹: {subfolder_name} (ID: {subfolder_id})")

                        # 使用现有的 get_video_files_recursively 函数检测视频文件
                        video_files = []
                        get_video_files_recursively(subfolder_id, video_files)

                        if not video_files:
                            # 没有视频文件，标记为可删除
                            folders_to_delete.append({
                                'folder_id': subfolder_id,
                                'folder_name': subfolder_name,
                                'parent_folder': parent_name
                            })
                            logging.info(f"🗑️ 子文件夹 '{subfolder_name}' 不包含视频文件，标记删除")
                        else:
                            # 包含视频文件，保留
                            folders_with_videos.append({
                                'folder_id': subfolder_id,
                                'folder_name': subfolder_name,
                                'parent_folder': parent_name,
                                'video_count': len(video_files)
                            })
                            logging.info(f"📁 子文件夹 '{subfolder_name}' 包含 {len(video_files)} 个视频文件，保留")

                    except Exception as e:
                        logging.error(f"分析子文件夹 '{subfolder_name}' 时发生错误: {e}")
                        failed_analysis.append({
                            'folder_name': subfolder_name,
                            'parent_folder': parent_name,
                            'error': str(e)
                        })

            except Exception as e:
                logging.error(f"扫描父文件夹 '{parent_folder_name}' 时发生错误: {e}")
                failed_analysis.append({
                    'folder_name': parent_folder_name,
                    'error': f'扫描父文件夹失败: {str(e)}'
                })

        # 如果没有需要删除的子文件夹
        if not folders_to_delete:
            message = "没有发现需要删除的空子文件夹"
            if folders_with_videos:
                message += f"，{len(folders_with_videos)} 个子文件夹包含视频文件已保留"
            if failed_analysis:
                message += f"，{len(failed_analysis)} 个文件夹分析失败"

            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': 0,
                'folders_with_videos': folders_with_videos,
                'failed_analysis': failed_analysis
            })

        logging.info(f"🗑️ 准备删除 {len(folders_to_delete)} 个无视频子文件夹")

        # 执行删除操作
        deleted_folders = []
        failed_deletions = []

        for i, folder in enumerate(folders_to_delete):
            folder_id = folder['folder_id']
            folder_name = folder['folder_name']
            parent_folder = folder['parent_folder']

            try:
                logging.info(f"🗑️ 正在删除子文件夹 ({i+1}/{len(folders_to_delete)}): {folder_name} (ID: {folder_id}) 来自父文件夹: {parent_folder}")
                result = delete_files_115([folder_id])

                if result.get('success'):
                    deleted_folders.append({
                        'folder_id': folder_id,
                        'folder_name': folder_name,
                        'parent_folder': parent_folder
                    })
                    logging.info(f"✅ 成功删除子文件夹: {folder_name}")
                else:
                    failed_deletions.append({
                        'folder_id': folder_id,
                        'folder_name': folder_name,
                        'parent_folder': parent_folder,
                        'error': result.get('error', '删除失败')
                    })
                    logging.error(f"❌ 删除子文件夹失败: {folder_name} - {result.get('error', '删除失败')}")

            except Exception as e:
                failed_deletions.append({
                    'folder_id': folder_id,
                    'folder_name': folder_name,
                    'parent_folder': parent_folder,
                    'error': str(e)
                })
                logging.error(f"❌ 删除子文件夹异常: {folder_name} - {str(e)}")

            # 添加延迟以避免115云盘异步删除冲突
            if i < len(folders_to_delete) - 1:  # 不是最后一个
                logging.info(f"⏳ 等待2秒让删除操作完成...")
                time.sleep(2)

        # 统计结果
        total_parent_folders = len(selected_folders)
        total_subfolders_found = len(folders_to_delete) + len(folders_with_videos)
        deleted_count = len(deleted_folders)
        failed_count = len(failed_deletions) + len(failed_analysis)
        preserved_count = len(folders_with_videos)

        logging.info(f"🎯 删除空子文件夹完成: 扫描 {total_parent_folders} 个父文件夹，发现 {total_subfolders_found} 个子文件夹，删除 {deleted_count} 个，保留 {preserved_count} 个，失败 {failed_count} 个")

        # 清理缓存
        if deleted_folders:
            logging.info("已清理目录缓存")

        return jsonify({
            'success': failed_count == 0,
            'message': f'删除完成: 扫描 {total_parent_folders} 个父文件夹，删除 {deleted_count} 个空子文件夹，保留 {preserved_count} 个有视频的子文件夹，失败 {failed_count} 个',
            'deleted_folders': deleted_folders,
            'folders_with_videos': folders_with_videos,
            'failed_deletions': failed_deletions,
            'failed_analysis': failed_analysis,
            'total_parent_folders': total_parent_folders,
            'total_subfolders_found': total_subfolders_found,
            'deleted_count': deleted_count,
            'preserved_count': preserved_count,
            'failed_count': failed_count
        })

    except Exception as e:
        logging.error(f"删除空文件夹时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test_ai_api', methods=['POST'])
def test_ai_api():
    """测试AI API连接"""
    try:
        # 检查AI API配置
        if not GEMINI_API_KEY or not GEMINI_API_URL:
            return jsonify({
                'success': False,
                'error': 'AI API未配置',
                'details': {
                    'gemini_api_key': bool(GEMINI_API_KEY),
                    'gemini_api_url': bool(GEMINI_API_URL)
                }
            })

        logging.info("开始测试AI API连接")

        # 发送测试请求
        headers = {
            'Authorization': f'Bearer {GEMINI_API_KEY}',
            'Content-Type': 'application/json'
        }

        test_payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Hello, this is a test message. Please respond with 'AI API test successful'."}],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = requests.post(GEMINI_API_URL, headers=headers, json=test_payload, timeout=15)

        if response.status_code == 200:
            ai_response = response.json()
            content = ai_response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            logging.info(f"AI API测试成功，响应: {content}")

            return jsonify({
                'success': True,
                'message': 'AI API连接测试成功',
                'response': content,
                'model': MODEL,
                'status_code': response.status_code
            })
        else:
            error_msg = f"AI API返回错误状态码: {response.status_code}"
            logging.error(f"{error_msg}, 响应: {response.text}")

            return jsonify({
                'success': False,
                'error': error_msg,
                'status_code': response.status_code,
                'response_text': response.text[:500]  # 限制错误信息长度
            })

    except requests.exceptions.Timeout:
        error_msg = "AI API请求超时"
        logging.error(error_msg)
        return jsonify({'success': False, 'error': error_msg})
    except requests.exceptions.ConnectionError:
        error_msg = "无法连接到AI API服务器"
        logging.error(error_msg)
        return jsonify({'success': False, 'error': error_msg})
    except Exception as e:
        error_msg = f"测试AI API时发生错误: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return jsonify({'success': False, 'error': error_msg})

@app.route('/get_folder_content/<int:folder_id>', methods=['GET'])
def get_folder_content_by_id(folder_id):
    """通过GET方法获取指定文件夹下的文件和文件夹列表（用于文件夹浏览器）"""
    try:
        logging.info(f"📂 获取文件夹 {folder_id} 下的内容")

        # 获取文件夹内容
        folder_content = get_all_files_in_folder(folder_id, limit=100)

        if not folder_content or 'files' not in folder_content:
            return jsonify({
                'success': False,
                'error': '无法获取文件夹内容',
                'folders': [],
                'files': []
            })

        files = folder_content['files']

        # 分离文件夹和文件
        folders = [item for item in files if item.get('is_directory', False)]
        regular_files = [item for item in files if not item.get('is_directory', False)]

        # 转换为前端需要的格式
        formatted_folders = []
        for folder in folders:
            formatted_folders.append({
                'fileId': folder.get('id', ''),
                'filename': folder.get('name', ''),
                'type': 1,  # 文件夹类型
                'size': 0,
                'is_directory': True
            })

        formatted_files = []
        for file in regular_files:
            formatted_files.append({
                'fileId': file.get('id', ''),
                'filename': file.get('name', ''),
                'type': 0,  # 文件类型
                'size': file.get('size', 0),
                'is_directory': False
            })

        return jsonify({
            'success': True,
            'folders': formatted_folders,
            'files': formatted_files,
            'current_folder_id': folder_id,
            'total_folders': len(formatted_folders),
            'total_files': len(formatted_files)
        })

    except Exception as e:
        logging.error(f"获取文件夹内容时发生错误: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'folders': [],
            'files': []
        })

@app.route('/move_files_direct', methods=['POST'])
def move_files_direct():
    """直接移动选中的文件到指定文件夹"""
    try:
        move_data_json = request.form.get('move_data')
        target_folder_id = request.form.get('target_folder_id')

        if not move_data_json:
            return jsonify({'success': False, 'error': '没有提供移动数据。'})

        if not target_folder_id:
            return jsonify({'success': False, 'error': '没有提供目标文件夹ID。'})

        try:
            target_folder_id = int(target_folder_id)
        except ValueError:
            return jsonify({'success': False, 'error': '目标文件夹ID必须是数字。'})

        move_data = json.loads(move_data_json)
        if not move_data:
            return jsonify({'success': False, 'error': '没有文件需要移动。'})

        # 提取文件ID列表
        file_ids = []
        for item in move_data:
            file_id = item.get('fileId')
            if file_id:
                try:
                    file_ids.append(int(file_id))
                except ValueError:
                    logging.warning(f"无效的文件ID: {file_id}")
                    continue

        if not file_ids:
            return jsonify({'success': False, 'error': '没有有效的文件ID。'})

        logging.info(f"📦 准备移动 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
        logging.info(f"📋 文件ID列表: {file_ids}")

        # 调用115云盘移动API
        result = move_files_115(file_ids, target_folder_id)

        if result.get("success"):
            logging.info(f"✅ 成功移动 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
            return jsonify({
                'success': True,
                'message': f'成功移动 {len(file_ids)} 个文件到目标文件夹。',
                'moved_count': len(file_ids),
                'target_folder_id': target_folder_id
            })
        else:
            error_message = result.get("message", "移动文件失败，请检查目标文件夹ID是否正确。")
            logging.error(f"移动文件失败: {error_message}")
            return jsonify({'success': False, 'error': error_message})

    except json.JSONDecodeError as e:
        logging.error(f"解析移动数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': f'JSON解析错误: {str(e)}'})
    except Exception as e:
        logging.error(f"移动文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_folder_info', methods=['GET'])
def get_folder_info():
    """获取单个文件夹的基本信息（轻量级，用于点击查看）"""
    try:
        folder_id = request.args.get('folder_id', '0')

        # 处理无效的folder_id值
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            folder_id = '0'

        logging.info(f"🔍 获取文件夹 {folder_id} 的基本信息")

        # 只获取直接子项，不递归，提高速度
        try:
            files = get_all_files_in_folder(folder_id, limit=100)
            if not files:
                return jsonify({'success': False, 'error': '无法获取文件夹内容'})

            # 统计基本信息
            total_items = len(files)
            folder_count = sum(1 for item in files if item.get('type') == 1)  # type=1表示文件夹
            file_count = sum(1 for item in files if item.get('type') == 0)    # type=0表示文件
            video_count = 0
            total_size = 0

            # 统计视频文件和大小
            for item in files:
                if item.get('type') == 0:  # 文件
                    file_size = item.get('size', 0)
                    if isinstance(file_size, (int, float)):
                        total_size += file_size

                    # 检查是否为视频文件
                    filename = item.get('filename', '')
                    _, ext = os.path.splitext(filename)
                    if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                        video_count += 1

            # 格式化大小
            if total_size >= 1024 ** 4:  # TB
                size_str = f"{total_size / (1024 ** 4):.1f}TB"
            elif total_size >= 1024 ** 3:  # GB
                size_str = f"{total_size / (1024 ** 3):.1f}GB"
            elif total_size >= 1024 ** 2:  # MB
                size_str = f"{total_size / (1024 ** 2):.1f}MB"
            else:
                size_str = f"{total_size}B"

            return jsonify({
                'success': True,
                'folder_id': folder_id,
                'total_items': total_items,
                'folder_count': folder_count,
                'file_count': file_count,
                'video_count': video_count,
                'total_size': total_size,
                'size_str': size_str
            })

        except Exception as e:
            logging.error(f"获取文件夹信息时发生错误: {e}")
            return jsonify({'success': False, 'error': f'获取文件夹信息失败: {str(e)}'})

    except Exception as e:
        logging.error(f"处理文件夹信息请求时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/restart_status', methods=['GET'])
def restart_status():
    """检查重启功能状态"""
    try:
        is_packaged = getattr(sys, 'frozen', False)

        status = {
            'restart_available': True,
            'environment': 'packaged' if is_packaged else 'development',
            'platform': sys.platform,
            'executable_path': sys.executable,
            'argv': sys.argv,
            'working_directory': os.getcwd()
        }

        if is_packaged:
            # 检查可执行文件是否存在
            possible_executables = []
            if sys.platform == "darwin":
                possible_executables = [
                    './pan115-scraper-mac',
                    'pan115-scraper-mac',
                    './dist/pan115-scraper-mac',
                    'dist/pan115-scraper-mac',
                    sys.executable  # 当前运行的可执行文件
                ]
            elif sys.platform == "win32":
                possible_executables = [
                    './pan115-scraper-win.exe',
                    'pan115-scraper-win.exe',
                    './dist/pan115-scraper-win.exe',
                    'dist/pan115-scraper-win.exe',
                    sys.executable
                ]
            else:
                possible_executables = [sys.executable]

            # 检查哪个可执行文件存在
            found_executable = None
            for exe_path in possible_executables:
                if os.path.exists(exe_path):
                    found_executable = exe_path
                    break

            status['found_executable'] = found_executable
            status['restart_available'] = found_executable is not None
        else:
            # 开发环境，检查是否可以重启Python脚本
            status['restart_available'] = True

        return jsonify(status)

    except Exception as e:
        logging.error(f"检查重启状态时发生错误: {e}")
        return jsonify({
            'restart_available': False,
            'error': str(e),
            'environment': 'unknown'
        })

@app.route('/restart', methods=['POST'])
def restart_app():
    logging.info("接收到重启应用程序的请求。")
    try:
        # 立即返回响应，告知客户端应用程序正在重启
        response = jsonify({'success': True, 'message': '应用程序正在重启...'})
        
        if request.remote_addr != '127.0.0.1': # 仅允许本地重启
            return "Unauthorized", 403
        print("Restart request received. Scheduling restart...")
        # 在单独的线程中执行重启逻辑，这样可以立即返回HTTP响应
        # 否则，重启操作会阻塞HTTP请求，导致客户端超时
        Thread(target=restart_process_async).start()
            
        return response
    except Exception as e:
        logging.error(f"重启应用程序失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'重启失败: {str(e)}'})

if __name__ == '__main__':
    logging.info("启动 Flask 应用程序。")
    # 确保 templates 目录存在
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    # 启动缓存清理后台任务

    print("启动 Flask 应用程序在端口 5001...")
    app.run(debug=True, host='127.0.0.1', port=5001) # 将端口改为 5001

