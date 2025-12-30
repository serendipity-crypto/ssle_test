import os
import glob
import pandas as pd
from collections import defaultdict


def analyze_benchmark_results(workdir="."):
    """
    分析指定工作目录中的 p*_id*.csv 文件
    """
    # 规范路径
    workdir = os.path.abspath(workdir)

    # 构造文件匹配路径
    file_pattern = os.path.join(workdir, "p*_id*.csv")

    files = glob.glob(file_pattern)

    if not files:
        print(f"未在目录 {workdir} 中找到匹配的文件 p*_id*.csv")
        return {}

    party_groups = defaultdict(list)

    for file in files:
        try:
            filename = os.path.basename(file)
            p_index = filename.find("p") + 1
            underscore_index = filename.find("_", p_index)
            num_parties = int(filename[p_index:underscore_index])
            party_groups[num_parties].append(file)
        except (ValueError, IndexError):
            print(f"无法从文件名中解析party数量: {file}")
            continue

    results = {}
    sorted_party_nums = sorted(party_groups.keys())

    for num_parties in sorted_party_nums:
        file_list = party_groups[num_parties]
        print(f"\n分析 {num_parties} 个party的文件:")
        print(f"找到 {len(file_list)} 个文件")

        round1_times = []
        round2_times = []

        for file in file_list:
            try:
                df = pd.read_csv(file)

                round1_data = df[df["Round"] == 0]["Time_ms"]
                round2_data = df[df["Round"] == 1]["Time_ms"]

                if not round1_data.empty:
                    round1_times.extend(round1_data.tolist())
                if not round2_data.empty:
                    round2_times.extend(round2_data.tolist())

                print(
                    f"  文件 {os.path.basename(file)}: 第1轮 {len(round1_data)} 条记录, 第2轮 {len(round2_data)} 条记录"
                )

            except Exception as e:
                print(f"  处理文件 {file} 时出错: {e}")
                continue

        # 统计 round1
        if round1_times:
            round1_avg = round(sum(round1_times) / len(round1_times), 3)
            round1_min = min(round1_times)
            round1_max = max(round1_times)
        else:
            round1_avg = round1_min = round1_max = 0.0

        # 统计 round2
        if round2_times:
            round2_avg = round(sum(round2_times) / len(round2_times), 3)
            round2_min = min(round2_times)
            round2_max = max(round2_times)
        else:
            round2_avg = round2_min = round2_max = 0.0

        results[num_parties] = {
            "round1_avg": round1_avg,
            "round1_min": round1_min,
            "round1_max": round1_max,
            "round1_count": len(round1_times),
            "round2_avg": round2_avg,
            "round2_min": round2_min,
            "round2_max": round2_max,
            "round2_count": len(round2_times),
        }

        print(f"  Party数量 {num_parties}:")
        print(
            f"    第1轮: 平均={round1_avg:.3f} ms, 最小={round1_min} ms, 最大={round1_max} ms (基于 {len(round1_times)} 条记录)"
        )
        print(
            f"    第2轮: 平均={round2_avg:.3f} ms, 最小={round2_min} ms, 最大={round2_max} ms (基于 {len(round2_times)} 条记录)"
        )

    return results


def save_results_to_csv(results, output_file="analysis.csv", workdir="."):
    """
    将分析结果保存到指定工作目录中
    """
    if not results:
        print("没有结果可保存")
        return

    workdir = os.path.abspath(workdir)
    os.makedirs(workdir, exist_ok=True)

    output_path = os.path.join(workdir, output_file)

    sorted_results = sorted(results.items(), key=lambda x: x[0])

    data = []
    for num_parties, stats in sorted_results:
        data.append(
            {
                "NumParties": num_parties,
                "Round1_Avg_Time_ms": stats["round1_avg"],
                "Round1_Min_Time_ms": stats["round1_min"],
                "Round1_Max_Time_ms": stats["round1_max"],
                "Round1_Record_Count": stats["round1_count"],
                "Round2_Avg_Time_ms": stats["round2_avg"],
                "Round2_Min_Time_ms": stats["round2_min"],
                "Round2_Max_Time_ms": stats["round2_max"],
                "Round2_Record_Count": stats["round2_count"],
            }
        )

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)

    print(f"\n结果已保存到: {output_path}")
    print("\nCSV文件内容预览:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    # path = "./251208/tcp_wan_results"
    # path = "./251230/relect_tcp_tree_lan_results"
    # path = "./251230/relect_tcp_pairwise_lan_results"
    # path = "./251230/qelect_tcp_pairwise_lan_results"
    path = "./251230/qelect_tcp_tree_lan_results"
    # ⭐ 这里指定工作目录，例如 "data" 或 "./results"
    analysis_results = analyze_benchmark_results(workdir=path)

    if analysis_results:
        save_results_to_csv(analysis_results, workdir=path)

    print("\n分析完成!")
