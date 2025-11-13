import os
import glob
import pandas as pd
from collections import defaultdict


def analyze_benchmark_results():
    # 查找所有符合条件的文件
    file_pattern = "benchmark_results_p*_id*_lan.csv"
    files = glob.glob(file_pattern)

    if not files:
        print("未找到匹配的文件")
        return {}

    # 按party数量分组文件
    party_groups = defaultdict(list)

    for file in files:
        # 从文件名中提取party数量
        try:
            # 查找"p"后面跟着数字的部分
            p_index = file.find("p") + 1
            underscore_index = file.find("_", p_index)
            num_parties = int(file[p_index:underscore_index])
            party_groups[num_parties].append(file)
        except (ValueError, IndexError):
            print(f"无法从文件名中解析party数量: {file}")
            continue

    # 分析每个party数量组
    results = {}

    # 按party数量排序
    sorted_party_nums = sorted(party_groups.keys())

    for num_parties in sorted_party_nums:
        file_list = party_groups[num_parties]
        print(f"\n分析 {num_parties} 个party的文件:")
        print(f"找到 {len(file_list)} 个文件")

        # 存储所有轮次的数据
        round1_times = []
        round2_times = []

        for file in file_list:
            try:
                df = pd.read_csv(file)

                # 筛选第1轮和第2轮的数据
                round1_data = df[df["Round"] == 1]["Time_ms"]
                round2_data = df[df["Round"] == 2]["Time_ms"]

                if not round1_data.empty:
                    round1_times.extend(round1_data.tolist())
                if not round2_data.empty:
                    round2_times.extend(round2_data.tolist())

                print(
                    f"  文件 {file}: 第1轮 {len(round1_data)} 条记录, 第2轮 {len(round2_data)} 条记录"
                )

            except Exception as e:
                print(f"  处理文件 {file} 时出错: {e}")
                continue

        # 计算平均值并保留3位小数
        if round1_times:
            round1_avg = round(sum(round1_times) / len(round1_times), 3)
        else:
            round1_avg = 0.0

        if round2_times:
            round2_avg = round(sum(round2_times) / len(round2_times), 3)
        else:
            round2_avg = 0.0

        results[num_parties] = {
            "round1_avg": round1_avg,
            "round2_avg": round2_avg,
            "round1_count": len(round1_times),
            "round2_count": len(round2_times),
        }

        print(f"  Party数量 {num_parties}:")
        print(
            f"    第1轮平均时间: {round1_avg:.3f} ms (基于 {len(round1_times)} 条记录)"
        )
        print(
            f"    第2轮平均时间: {round2_avg:.3f} ms (基于 {len(round2_times)} 条记录)"
        )

    return results


def save_results_to_csv(results, output_file="benchmark_analysis.csv"):
    """将结果保存到CSV文件"""
    if not results:
        print("没有结果可保存")
        return

    # 按party数量排序
    sorted_results = sorted(results.items(), key=lambda x: x[0])

    data = []
    for num_parties, stats in sorted_results:
        data.append(
            {
                "NumParties": num_parties,
                "Round1_Avg_Time_ms": stats["round1_avg"],
                "Round2_Avg_Time_ms": stats["round2_avg"],
                "Round1_Record_Count": stats["round1_count"],
                "Round2_Record_Count": stats["round2_count"],
            }
        )

    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n结果已保存到: {output_file}")

    # 打印CSV内容预览
    print("\nCSV文件内容预览:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    # 执行分析
    analysis_results = analyze_benchmark_results()

    # 保存结果到CSV文件
    if analysis_results:
        save_results_to_csv(analysis_results)

    print("\n分析完成!")
