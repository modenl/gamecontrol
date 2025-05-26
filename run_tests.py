#!/usr/bin/env python3
"""
GameTimeLimiter 测试运行器

这个脚本用于运行所有的集成测试。
遵循AI开发规范：只运行可重复执行的测试。
"""

import sys
import os
import unittest
import importlib.util
from pathlib import Path


def discover_integration_tests():
    """发现所有的集成测试文件"""
    test_files = []
    integration_dir = Path(__file__).parent / "tests" / "integration"
    
    if integration_dir.exists():
        for test_file in integration_dir.glob("test_integration_*.py"):
            test_files.append(test_file)
    
    return test_files


def load_test_module(test_file_path):
    """动态加载测试模块"""
    module_name = test_file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, test_file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_all_integration_tests():
    """运行所有集成测试"""
    print("🚀 GameTimeLimiter 集成测试套件")
    print("=" * 60)
    
    # 发现测试文件
    test_files = discover_integration_tests()
    
    if not test_files:
        print("❌ 未找到集成测试文件")
        return False
    
    print(f"📁 发现 {len(test_files)} 个集成测试文件:")
    for test_file in test_files:
        print(f"   - {test_file.name}")
    print()
    
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 加载所有测试
    for test_file in test_files:
        try:
            print(f"📥 加载测试: {test_file.name}")
            module = load_test_module(test_file)
            
            # 查找测试类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, unittest.TestCase) and 
                    attr != unittest.TestCase):
                    
                    tests = unittest.TestLoader().loadTestsFromTestCase(attr)
                    suite.addTests(tests)
                    print(f"   ✅ 加载测试类: {attr_name}")
        
        except Exception as e:
            print(f"   ❌ 加载失败: {e}")
            return False
    
    print()
    
    # 运行测试
    print("🧪 开始运行集成测试...")
    print("-" * 60)
    
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        buffer=True
    )
    
    result = runner.run(suite)
    
    # 输出结果摘要
    print("\n" + "=" * 60)
    print("📊 测试结果摘要")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    
    print(f"总测试数: {total_tests}")
    print(f"成功: {total_tests - failures - errors - skipped}")
    print(f"失败: {failures}")
    print(f"错误: {errors}")
    print(f"跳过: {skipped}")
    
    if result.wasSuccessful():
        print("\n🎉 所有集成测试通过！")
        return True
    else:
        print("\n💥 部分集成测试失败！")
        
        if result.failures:
            print("\n❌ 失败的测试:")
            for test, traceback in result.failures:
                print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\n🚨 错误的测试:")
            for test, traceback in result.errors:
                print(f"   - {test}: {traceback.split('Exception:')[-1].strip()}")
        
        return False


def main():
    """主函数"""
    try:
        success = run_all_integration_tests()
        sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n\n💥 运行测试时发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 