"""
網格交易本金計算器
輸入網格參數，自動計算所需本金
"""

def calculate_grid_capital(lower_price, upper_price, grid_num, quantity_per_grid):
    """
    計算網格交易所需本金

    Args:
        lower_price: 網格下限價格
        upper_price: 網格上限價格
        grid_num: 網格數量
        quantity_per_grid: 每格交易數量（張）

    Returns:
        dict: 包含各種計算結果
    """
    # 計算網格間距
    grid_spacing = (upper_price - lower_price) / grid_num

    # 計算每個網格點的價格和所需資金
    grid_levels = []
    total_cost = 0

    for i in range(grid_num + 1):
        price = lower_price + (i * grid_spacing)
        cost = price * 1000 * quantity_per_grid  # 每張 = 1000 股

        grid_levels.append({
            'level': i,
            'price': round(price, 2),
            'cost': cost
        })

    # 最大可能買入的次數（不包括最高點，因為最高點只賣不買）
    max_buy_count = grid_num

    # 最壞情況：價格跌到最低點，所有網格都買入
    # 使用最低價計算，因為越低價格買入越多次
    worst_case_capital = lower_price * 1000 * quantity_per_grid * max_buy_count

    # 平均情況：使用平均價格計算
    avg_price = (lower_price + upper_price) / 2
    avg_case_capital = avg_price * 1000 * quantity_per_grid * max_buy_count

    return {
        'grid_spacing': round(grid_spacing, 2),
        'grid_levels': grid_levels,
        'max_buy_count': max_buy_count,
        'worst_case_capital': worst_case_capital,  # 最壞情況所需本金
        'avg_case_capital': avg_case_capital,      # 平均情況所需本金
        'recommended_capital': worst_case_capital * 1.2  # 建議本金（含 20% 緩衝）
    }


def print_capital_report(lower_price, upper_price, grid_num, quantity_per_grid):
    """
    打印本金需求報告
    """
    result = calculate_grid_capital(lower_price, upper_price, grid_num, quantity_per_grid)

    print("=" * 60)
    print("網格交易本金需求計算報告")
    print("=" * 60)

    print(f"\n【網格參數】")
    print(f"  價格區間: {lower_price} ~ {upper_price}")
    print(f"  網格數量: {grid_num}")
    print(f"  網格間距: {result['grid_spacing']}")
    print(f"  每格數量: {quantity_per_grid} 張")
    print(f"  最大買入次數: {result['max_buy_count']} 次")

    print(f"\n【本金需求】")
    print(f"  最壞情況（買滿所有網格）: ${result['worst_case_capital']:,.0f}")
    print(f"  平均情況: ${result['avg_case_capital']:,.0f}")
    print(f"  建議準備本金: ${result['recommended_capital']:,.0f} (含20%緩衝)")

    print(f"\n【詳細網格資訊】")
    print(f"  {'層級':<6} {'價格':>10} {'單次成本':>15}")
    print(f"  {'-'*6} {'-'*10} {'-'*15}")

    for level_info in result['grid_levels']:
        print(f"  Level {level_info['level']:<2} {level_info['price']:>10.2f} ${level_info['cost']:>14,.0f}")

    print(f"\n【資金使用說明】")
    print(f"  • 最壞情況: 價格跌到最低點，所有 {result['max_buy_count']} 個買入點都觸發")
    print(f"  • 計算公式: 最低價 × 1000股 × {quantity_per_grid}張 × {result['max_buy_count']}格")
    print(f"  • 建議準備: 最壞情況 × 1.2 = ${result['recommended_capital']:,.0f}")
    print(f"  • 額外 20%: 用於應對價格波動和手續費")

    print("\n" + "=" * 60)

    return result


if __name__ == "__main__":
    print("網格交易本金計算器\n")

    # 從用戶輸入獲取參數
    try:
        print("請輸入網格參數：")
        lower_price = float(input("網格下限價格: "))
        upper_price = float(input("網格上限價格: "))
        grid_num = int(input("網格數量: "))
        quantity_per_grid = int(input("每格交易數量（張）: "))

        print("\n")
        result = print_capital_report(lower_price, upper_price, grid_num, quantity_per_grid)

        # 詢問是否要更新配置文件
        print("\n是否要將建議本金更新到 config/grid_config_example.py？")
        update = input("輸入 'y' 確認更新，其他鍵取消: ")

        if update.lower() == 'y':
            print(f"\n建議在配置文件中設定：")
            print(f"MAX_CAPITAL = {int(result['recommended_capital'])}  # 建議本金")
            print(f"\n請手動更新配置文件。")

    except ValueError as e:
        print(f"\n輸入錯誤: {e}")
        print("請輸入有效的數字。")
    except KeyboardInterrupt:
        print("\n\n已取消")
