#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试三角形高度计算问题
验证是否解决了prompt答案格式限制的问题
"""

def test_triangle_calculation():
    """验证三角形ABC高度计算"""
    
    # 给定：AB = 7, BC = 24, AC = 25
    AB = 7
    BC = 24
    AC = 25
    
    print("=== 三角形ABC分析 ===")
    print(f"边长：AB = {AB}, BC = {BC}, AC = {AC}")
    
    # 1. 检查是否为直角三角形
    print(f"\n1. 检查勾股定理：")
    print(f"   AB² + BC² = {AB}² + {BC}² = {AB**2} + {BC**2} = {AB**2 + BC**2}")
    print(f"   AC² = {AC}² = {AC**2}")
    
    is_right_triangle = (AB**2 + BC**2) == AC**2
    print(f"   是否为直角三角形：{is_right_triangle}")
    
    if is_right_triangle:
        print(f"   直角在点B（因为AC是最长边，对应的角是直角）")
    
    # 2. 计算从B到AC的高度
    print(f"\n2. 计算从B到AC的高度：")
    
    # 方法1：面积法
    area_method1 = 0.5 * AB * BC  # 直角三角形面积
    print(f"   面积 = 1/2 × AB × BC = 1/2 × {AB} × {BC} = {area_method1}")
    
    # 面积也等于：1/2 × 底边 × 高
    # 1/2 × AC × h = area_method1
    # h = 2 × area_method1 / AC
    altitude = (2 * area_method1) / AC
    print(f"   面积 = 1/2 × AC × h")
    print(f"   {area_method1} = 1/2 × {AC} × h")
    print(f"   h = 2 × {area_method1} / {AC} = {altitude}")
    
    # 转换为分数形式
    numerator = 2 * int(area_method1)
    denominator = AC
    print(f"   h = {numerator}/{denominator} = {altitude}")
    
    # 3. 验证答案格式
    print(f"\n3. 答案格式分析：")
    print(f"   精确值：{altitude}")
    print(f"   保留2位小数：{altitude:.2f}")
    
    # 检查是否为简单分数
    from fractions import Fraction
    frac = Fraction(numerator, denominator)
    print(f"   简化分数：{frac}")
    print(f"   小数形式：{float(frac)}")
    
    print(f"\n=== 结论 ===")
    print(f"正确答案应该是：{altitude}")
    print(f"GPT给出的答案7是错误的")
    print(f"可能的原因：prompt限制答案为整数或简单分数")

def test_answer_tolerance():
    """测试答案容差计算"""
    
    print("\n=== 答案容差测试 ===")
    
    def calculate_tolerance(standard_num):
        """计算容差（模拟改进后的逻辑）"""
        if standard_num == 0:
            return 0.01
        elif abs(standard_num) < 1:
            return 0.01  # 小数用固定小容差
        elif abs(standard_num) < 100:
            return max(0.01, abs(standard_num) * 0.02)  # 2%相对误差，但至少0.01
        else:
            return abs(standard_num) * 0.01  # 大数用1%相对误差
    
    test_cases = [
        (6.72, 6.7),   # 用户答案6.7，标准答案6.72
        (6.72, 6.72),  # 完全匹配
        (6.72, 6.8),   # 用户答案6.8
        (6.72, 7),     # 用户答案7（错误）
        (15, 15),      # 整数匹配
        (15, 14.99),   # 接近整数
    ]
    
    for standard, user in test_cases:
        tolerance = calculate_tolerance(standard)
        diff = abs(user - standard)
        is_correct = diff <= tolerance
        
        print(f"标准答案:{standard:6.2f}, 用户答案:{user:6.2f}, "
              f"差值:{diff:6.3f}, 容差:{tolerance:6.3f}, "
              f"正确:{is_correct}")

if __name__ == "__main__":
    test_triangle_calculation()
    test_answer_tolerance() 