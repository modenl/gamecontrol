#!/usr/bin/env python3
"""
集成测试运行器 - 运行所有集成测试并生成报告
"""
import os
import sys
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegrationTestRunner:
    """集成测试运行器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_dir = self.project_root / "tests" / "integration"
        self.results = []
        
    def discover_test_files(self) -> List[Path]:
        """发现所有集成测试文件"""
        test_files = []
        
        if not self.test_dir.exists():
            logger.warning(f"测试目录不存在: {self.test_dir}")
            return test_files
        
        # 查找所有test_*.py文件（除了test_framework.py）
        for test_file in self.test_dir.glob("test_*.py"):
            if test_file.name != "test_framework.py":
                test_files.append(test_file)
        
        # 优先运行核心集成测试
        core_test = self.test_dir / "test_core_integration.py"
        if core_test in test_files:
            test_files.remove(core_test)
            test_files.insert(0, core_test)
            logger.info("📌 核心集成测试将优先运行")
        
        logger.info(f"发现 {len(test_files)} 个测试文件")
        for i, test_file in enumerate(test_files):
            priority = "🥇" if i == 0 and test_file.name == "test_core_integration.py" else "  "
            logger.info(f"{priority} - {test_file.name}")
        
        return test_files
    
    def run_test_file(self, test_file: Path) -> Tuple[bool, str, float]:
        """运行单个测试文件"""
        logger.info(f"🧪 运行测试文件: {test_file.name}")
        
        start_time = time.time()
        
        try:
            # 设置环境变量
            env = os.environ.copy()
            env['GAMECONTROL_TEST_MODE'] = 'true'
            env['PYTHONPATH'] = str(self.project_root)
            env['PYTHONIOENCODING'] = 'utf-8'  # 确保Python使用UTF-8编码
            env['LANG'] = 'en_US.UTF-8'  # 设置语言环境
            
            # 运行测试
            result = subprocess.run(
                [sys.executable, str(test_file)],
                cwd=str(self.project_root),
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 替换无法解码的字符
                timeout=300  # 5分钟超时
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"✅ {test_file.name} 通过 ({duration:.2f}s)")
                return True, result.stdout, duration
            else:
                logger.error(f"❌ {test_file.name} 失败 ({duration:.2f}s)")
                logger.error(f"错误输出:\n{result.stderr}")
                return False, result.stderr, duration
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            error_msg = f"测试超时 ({duration:.2f}s)"
            logger.error(f"⏰ {test_file.name} {error_msg}")
            return False, error_msg, duration
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"运行测试时出错: {e}"
            logger.error(f"💥 {test_file.name} {error_msg}")
            return False, error_msg, duration
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        logger.info("🚀 开始运行所有集成测试")
        
        test_files = self.discover_test_files()
        
        if not test_files:
            logger.warning("没有发现任何测试文件")
            return {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'results': [],
                'duration': 0
            }
        
        start_time = time.time()
        results = []
        passed = 0
        failed = 0
        
        for test_file in test_files:
            success, output, duration = self.run_test_file(test_file)
            
            result = {
                'file': test_file.name,
                'success': success,
                'output': output,
                'duration': duration
            }
            
            results.append(result)
            
            if success:
                passed += 1
            else:
                failed += 1
        
        total_duration = time.time() - start_time
        
        return {
            'total': len(test_files),
            'passed': passed,
            'failed': failed,
            'results': results,
            'duration': total_duration
        }
    
    def generate_report(self, test_results: Dict[str, Any]) -> str:
        """生成测试报告"""
        report = []
        report.append("=" * 80)
        report.append("🧪 集成测试报告")
        report.append("=" * 80)
        report.append("")
        
        # 总体统计
        total = test_results['total']
        passed = test_results['passed']
        failed = test_results['failed']
        duration = test_results['duration']
        
        report.append(f"📊 总体统计:")
        report.append(f"   总测试文件: {total}")
        report.append(f"   ✅ 通过: {passed}")
        report.append(f"   ❌ 失败: {failed}")
        report.append(f"   ⏱️ 总耗时: {duration:.2f}s")
        report.append("")
        
        # 成功率
        if total > 0:
            success_rate = (passed / total) * 100
            report.append(f"📈 成功率: {success_rate:.1f}%")
        else:
            report.append("📈 成功率: N/A")
        report.append("")
        
        # 详细结果
        report.append("📋 详细结果:")
        report.append("-" * 40)
        
        for result in test_results['results']:
            file_name = result['file']
            success = result['success']
            duration = result['duration']
            
            status = "✅ 通过" if success else "❌ 失败"
            report.append(f"{status} {file_name} ({duration:.2f}s)")
            
            if not success:
                # 显示失败的详细信息
                output_lines = result['output'].split('\n')
                for line in output_lines[-10:]:  # 显示最后10行
                    if line.strip():
                        report.append(f"     {line}")
                report.append("")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report(self, report: str, filename: str = "integration_test_report.txt"):
        """保存测试报告到文件"""
        report_path = self.project_root / filename
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"📄 测试报告已保存到: {report_path}")
            
        except Exception as e:
            logger.error(f"保存测试报告失败: {e}")
    
    def check_environment(self) -> bool:
        """检查测试环境"""
        logger.info("🔍 检查测试环境...")
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version < (3, 8):
            logger.error(f"Python版本过低: {python_version}, 需要3.8+")
            return False
        
        logger.info(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # 检查必要的包
        required_packages = ['PyQt6', 'qasync', 'openai']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"✅ {package} 已安装")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"❌ {package} 未安装")
        
        if missing_packages:
            logger.error(f"缺少必要的包: {missing_packages}")
            logger.error("请运行: pip install -r requirements.txt")
            return False
        
        # 检查测试目录
        if not self.test_dir.exists():
            logger.error(f"测试目录不存在: {self.test_dir}")
            return False
        
        logger.info(f"✅ 测试目录: {self.test_dir}")
        
        logger.info("✅ 测试环境检查通过")
        return True

def main():
    """主函数"""
    logger.info("🎯 集成测试运行器启动")
    
    runner = IntegrationTestRunner()
    
    # 检查环境
    if not runner.check_environment():
        logger.error("❌ 环境检查失败，退出")
        return 1
    
    # 运行测试
    test_results = runner.run_all_tests()
    
    # 生成报告
    report = runner.generate_report(test_results)
    
    # 输出报告
    print("\n" + report)
    
    # 保存报告
    runner.save_report(report)
    
    # 返回退出码
    if test_results['failed'] == 0:
        logger.info("🎉 所有测试通过！")
        return 0
    else:
        logger.error(f"💥 {test_results['failed']} 个测试失败")
        return 1

if __name__ == "__main__":
    exit(main()) 