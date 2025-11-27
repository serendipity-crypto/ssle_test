import math
import os
import glob
import pandas as pd
from collections import defaultdict


def analyze_benchmark_results():
    # 查找所有符合条件的文件
    file_pattern = "benchmark_results_p*_id*_wan.csv"
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

        log_n = int(round(math.log2(num_parties)))

        # 存储所有轮次的数据
        round1_times = []
        round2_times = []
        round1_send_times = [[] for _ in range(log_n)]
        round1_recv_times = [[] for _ in range(log_n)]
        round2_send_times = [[] for _ in range(log_n)]
        round2_recv_times = [[] for _ in range(log_n)]

        for file in file_list:
            try:
                df = pd.read_csv(file)

                # 筛选第1轮和第2轮的数据
                round1_data = df[df["Round"] == 1]["TotalTime_ms"]
                round2_data = df[df["Round"] == 2]["TotalTime_ms"]
                round1_send_data = [
                    df[df["Round"] == 1][f"SendToPeer{i}_ms"] for i in range(log_n)
                ]
                round1_recv_data = [
                    df[df["Round"] == 1][f"RecvFromPeer{i}_ms"] for i in range(log_n)
                ]
                round2_send_data = [
                    df[df["Round"] == 2][f"SendToPeer{i}_ms"] for i in range(log_n)
                ]
                round2_recv_data = [
                    df[df["Round"] == 2][f"RecvFromPeer{i}_ms"] for i in range(log_n)
                ]

                for i in range(log_n):
                    if not round1_send_data[i].empty:
                        round1_send_times[i].extend(round1_send_data[i].tolist())
                    if not round1_recv_data[i].empty:
                        round1_recv_times[i].extend(round1_recv_data[i].tolist())
                    if not round2_send_data[i].empty:
                        round2_send_times[i].extend(round2_send_data[i].tolist())
                    if not round2_recv_data[i].empty:
                        round2_recv_times[i].extend(round2_recv_data[i].tolist())

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

        round1_send_avg = [0.0 for _ in range(7)]
        round1_recv_avg = [0.0 for _ in range(7)]
        round2_send_avg = [0.0 for _ in range(7)]
        round2_recv_avg = [0.0 for _ in range(7)]
        for i in range(log_n):
            if round1_send_times[i]:
                round1_send_avg[i] = round(
                    sum(round1_send_times[i]) / len(round1_send_times[i]), 3
                )
            if round1_recv_times[i]:
                round1_recv_avg[i] = round(
                    sum(round1_recv_times[i]) / len(round1_recv_times[i]), 3
                )
            if round2_send_times[i]:
                round2_send_avg[i] = round(
                    sum(round2_send_times[i]) / len(round2_send_times[i]), 3
                )
            if round2_recv_times[i]:
                round2_recv_avg[i] = round(
                    sum(round2_recv_times[i]) / len(round2_recv_times[i]), 3
                )

        results[num_parties] = {
            "round1_avg": round1_avg,
            "round2_avg": round2_avg,
            "round1_count": len(round1_times),
            "round2_count": len(round2_times),
        }

        for i in range(7):
            results[num_parties][f"Round1SendToPeer{i}_avg"] = round1_send_avg[i]
            results[num_parties][f"Round1RecvFromPeer{i}_avg"] = round1_recv_avg[i]
            results[num_parties][f"Round2SendToPeer{i}_avg"] = round2_send_avg[i]
            results[num_parties][f"Round2RecvFromPeer{i}_avg"] = round2_recv_avg[i]

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
                "Round1SendToPeer0_avg": stats["Round1SendToPeer0_avg"],
                "Round1SendToPeer1_avg": stats["Round1SendToPeer1_avg"],
                "Round1SendToPeer2_avg": stats["Round1SendToPeer2_avg"],
                "Round1SendToPeer3_avg": stats["Round1SendToPeer3_avg"],
                "Round1SendToPeer4_avg": stats["Round1SendToPeer4_avg"],
                "Round1SendToPeer5_avg": stats["Round1SendToPeer5_avg"],
                "Round1SendToPeer6_avg": stats["Round1SendToPeer6_avg"],
                "Round1RecvFromPeer0_avg": stats["Round1RecvFromPeer0_avg"],
                "Round1RecvFromPeer1_avg": stats["Round1RecvFromPeer1_avg"],
                "Round1RecvFromPeer2_avg": stats["Round1RecvFromPeer2_avg"],
                "Round1RecvFromPeer3_avg": stats["Round1RecvFromPeer3_avg"],
                "Round1RecvFromPeer4_avg": stats["Round1RecvFromPeer4_avg"],
                "Round1RecvFromPeer5_avg": stats["Round1RecvFromPeer5_avg"],
                "Round1RecvFromPeer6_avg": stats["Round1RecvFromPeer6_avg"],
                "Round2SendToPeer0_avg": stats["Round2SendToPeer0_avg"],
                "Round2SendToPeer1_avg": stats["Round2SendToPeer1_avg"],
                "Round2SendToPeer2_avg": stats["Round2SendToPeer2_avg"],
                "Round2SendToPeer3_avg": stats["Round2SendToPeer3_avg"],
                "Round2SendToPeer4_avg": stats["Round2SendToPeer4_avg"],
                "Round2SendToPeer5_avg": stats["Round2SendToPeer5_avg"],
                "Round2SendToPeer6_avg": stats["Round2SendToPeer6_avg"],
                "Round2RecvFromPeer0_avg": stats["Round2RecvFromPeer0_avg"],
                "Round2RecvFromPeer1_avg": stats["Round2RecvFromPeer1_avg"],
                "Round2RecvFromPeer2_avg": stats["Round2RecvFromPeer2_avg"],
                "Round2RecvFromPeer3_avg": stats["Round2RecvFromPeer3_avg"],
                "Round2RecvFromPeer4_avg": stats["Round2RecvFromPeer4_avg"],
                "Round2RecvFromPeer5_avg": stats["Round2RecvFromPeer5_avg"],
                "Round2RecvFromPeer6_avg": stats["Round2RecvFromPeer6_avg"],
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
