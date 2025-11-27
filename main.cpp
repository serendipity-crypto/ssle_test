#include <emp-tool/emp-tool.h>
#include <vector>
#include <string>
#include <chrono>
#include <map>
#include <fstream>
#include <iostream>
#include <random>
#include <iomanip>
#include <sstream>
#include <cassert>

const size_t round_count = 10;

class ShareBenchmarkTwoRounds
{
private:
    int party_id;
    int num_parties;
    int log_n;
    std::vector<emp::NetIO *> ios;
    std::vector<uint8_t> recv_buffers; // 预分配的接收缓冲区
    std::mt19937 rng_engine;

    // 详细时间记录结构
    struct TimeRecord
    {
        double connection_time_ms;                                // 建立连接的时间
        std::vector<std::vector<double>> round_times;             // [轮数][迭代次数] 每轮总时间
        std::vector<std::vector<std::vector<double>>> send_times; // [轮数][迭代次数][对等方] 发送时间
        std::vector<std::vector<std::vector<double>>> recv_times; // [轮数][迭代次数][对等方] 接收时间
    };

    TimeRecord detailed_times;

public:
    ShareBenchmarkTwoRounds(int party_id, int num_parties);
    ~ShareBenchmarkTwoRounds();

    // 网络设置
    bool setup_connections(const std::vector<std::string> &ips, int base_port);

    // 两轮测试函数
    void run_two_rounds_test(const std::vector<size_t> &data_sizes,
                             const std::string &output_csv_1 = "benchmark_results.csv", const std::string &output_csv_2 = "connection_results.csv");

private:
    void benchmark_round(size_t data_size, int round_index, int iterations = 5);
    void share_data(size_t size, std::vector<double> &send_times, std::vector<double> &recv_times);
    void generate_random_data(size_t size);
    void write_connection_to_csv(const std::vector<std::pair<size_t, double>> &results,
                                 const std::string &filename);
    void write_detailed_times_to_csv(const std::vector<size_t> &data_sizes,
                                     const std::string &filename);
    void preallocate_buffers(size_t data_size);

    bool is_power_of_two(int n) const { return (n & (n - 1)) == 0; }
    void validate_data_size(size_t data_size) const;
};

ShareBenchmarkTwoRounds::ShareBenchmarkTwoRounds(int pid, int nparties)
    : party_id(pid), num_parties(nparties), rng_engine(std::random_device{}())
{
    if (!is_power_of_two(num_parties))
    {
        throw std::invalid_argument("Number of parties must be a power of two");
    }

    log_n = 0;
    int temp = num_parties;
    while (temp > 1)
    {
        temp >>= 1;
        log_n++;
    }

    std::cout << "log_n " << log_n << std::endl;
    ios.resize(log_n, nullptr);

    // 初始化详细时间记录
    detailed_times.round_times.resize(2); // 两轮测试
    detailed_times.send_times.resize(2);
    detailed_times.recv_times.resize(2);
}

void ShareBenchmarkTwoRounds::validate_data_size(size_t data_size) const
{
    if (data_size == 0)
    {
        throw std::invalid_argument("Data size cannot be zero");
    }

    // 检查缓冲区大小不会溢出
    if (num_parties > SIZE_MAX / data_size)
    {
        throw std::overflow_error("Buffer size would overflow");
    }
}

ShareBenchmarkTwoRounds::~ShareBenchmarkTwoRounds()
{
    for (auto io : ios)
    {
        if (io)
            delete io;
    }
}

bool ShareBenchmarkTwoRounds::setup_connections(const std::vector<std::string> &ips, int base_port)
{
    auto connection_start = std::chrono::high_resolution_clock::now();

    try
    {
        int mask = 1;
        for (size_t i = 0; i < log_n; ++i)
        {
            int peer_id = party_id ^ mask;

            if (peer_id < party_id)
            {
                int port = base_port + party_id * num_parties + peer_id;
                std::cout << "Party " << party_id << " connecting to Party " << peer_id << " from port " << port << std::endl;
                ios[i] = new emp::NetIO(ips[peer_id].c_str(), port);
            }
            else
            {
                int port = base_port + peer_id * num_parties + party_id;
                std::cout << "Party " << party_id << " listening on port " << port << " for Party " << peer_id << std::endl;
                ios[i] = new emp::NetIO(nullptr, port);
            }
            mask <<= 1;
        }

        auto connection_end = std::chrono::high_resolution_clock::now();
        auto connection_duration = std::chrono::duration_cast<std::chrono::microseconds>(connection_end - connection_start);
        detailed_times.connection_time_ms = connection_duration.count() / 1000.0;

        std::cout << "Connection setup time: " << detailed_times.connection_time_ms << " ms" << std::endl;

        return true;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Network setup error: " << e.what() << std::endl;
        return false;
    }
}

void ShareBenchmarkTwoRounds::generate_random_data(size_t size)
{
    std::uniform_int_distribution<uint8_t> dis(0, 255);
    size_t start_offset = party_id * size;

    for (size_t i = 0; i < size; i++)
    {
        recv_buffers[start_offset + i] = dis(rng_engine);
    }
}

void ShareBenchmarkTwoRounds::preallocate_buffers(size_t data_size)
{
    validate_data_size(data_size);

    recv_buffers.resize(num_parties * data_size);
}

void ShareBenchmarkTwoRounds::share_data(size_t data_size,
                                         std::vector<double> &send_times, std::vector<double> &recv_times)
{
    int mask = 1;
    size_t current_offset = party_id * data_size;
    size_t current_size = data_size;

    std::chrono::microseconds send_duration;
    std::chrono::microseconds recv_duration;

    for (int i = 0; i < log_n; i++)
    {
        int peer_id = party_id ^ mask;

        if (party_id < peer_id)
        {
            auto send_start = std::chrono::high_resolution_clock::now();
            ios[i]->send_data(recv_buffers.data() + current_offset, current_size);
            ios[i]->flush();
            auto send_end = std::chrono::high_resolution_clock::now();

            auto recv_start = send_end;
            ios[i]->recv_data(recv_buffers.data() + current_offset + current_size, current_size);
            auto recv_end = std::chrono::high_resolution_clock::now();

            send_duration = std::chrono::duration_cast<std::chrono::microseconds>(send_end - send_start);
            recv_duration = std::chrono::duration_cast<std::chrono::microseconds>(recv_end - recv_start);
        }
        else
        {
            auto recv_start = std::chrono::high_resolution_clock::now();
            ios[i]->recv_data(recv_buffers.data() + current_offset - current_size, current_size);
            auto recv_end = std::chrono::high_resolution_clock::now();

            auto send_start = recv_end;
            ios[i]->send_data(recv_buffers.data() + current_offset, current_size);
            ios[i]->flush();
            auto send_end = std::chrono::high_resolution_clock::now();
            current_offset -= current_size;

            send_duration = std::chrono::duration_cast<std::chrono::microseconds>(send_end - send_start);
            recv_duration = std::chrono::duration_cast<std::chrono::microseconds>(recv_end - recv_start);
        }

        send_times[i] = send_duration.count() / 1000.0;
        recv_times[i] = recv_duration.count() / 1000.0;

        mask <<= 1;
        current_size *= 2;
    }
}

void ShareBenchmarkTwoRounds::benchmark_round(size_t data_size, int round_index, int iterations)
{
    // 预分配缓冲区
    preallocate_buffers(data_size);

    generate_random_data(data_size);

    // 预热
    std::vector<double> warmup_send_times(log_n, 0.0);
    std::vector<double> warmup_recv_times(log_n, 0.0);
    share_data(data_size, warmup_send_times, warmup_recv_times);

    // 为当前轮次初始化时间记录
    detailed_times.round_times[round_index].resize(iterations);
    detailed_times.send_times[round_index].resize(iterations);
    detailed_times.recv_times[round_index].resize(iterations);

    for (int i = 0; i < iterations; i++)
    {
        auto round_start = std::chrono::high_resolution_clock::now();

        // 初始化当前迭代的时间记录
        detailed_times.send_times[round_index][i].resize(log_n, 0.0);
        detailed_times.recv_times[round_index][i].resize(log_n, 0.0);

        share_data(data_size, detailed_times.send_times[round_index][i],
                   detailed_times.recv_times[round_index][i]);

        auto round_end = std::chrono::high_resolution_clock::now();
        auto round_duration = std::chrono::duration_cast<std::chrono::microseconds>(round_end - round_start);
        detailed_times.round_times[round_index][i] = round_duration.count() / 1000.0;
    }
}

void ShareBenchmarkTwoRounds::write_connection_to_csv(const std::vector<std::pair<size_t, double>> &results,
                                                      const std::string &filename)
{
    std::ofstream file(filename);
    if (!file.is_open())
    {
        std::cerr << "Failed to open CSV file: " << filename << std::endl;
        return;
    }

    // 写入CSV头部
    file << "ConnectionTime_ms" << std::endl;

    file << detailed_times.connection_time_ms << std::endl;

    file.close();
    std::cout << "Results written to: " << filename << std::endl;
}

void ShareBenchmarkTwoRounds::write_detailed_times_to_csv(const std::vector<size_t> &data_sizes,
                                                          const std::string &filename)
{
    std::ofstream file(filename);
    if (!file.is_open())
    {
        std::cerr << "Failed to open detailed CSV file: " << filename << std::endl;
        return;
    }

    // 写入CSV头部
    file << "Round,Iteration,DataSize_KB,DataSize_Bytes,TotalTime_ms";

    // 添加每个对等方的发送和接收时间列
    for (int i = 0; i < log_n; i++)
    {
        file << ",SendToPeer" << i << "_ms";
        file << ",RecvFromPeer" << i << "_ms";
    }
    file << ",PartyID,NumParties" << std::endl;

    // 写入每轮的详细时间
    for (int round = 0; round < 2; round++)
    {
        for (size_t iter = 0; iter < detailed_times.round_times[round].size(); iter++)
        {
            file << (round + 1) << "," << (iter + 1) << ","
                 << (data_sizes[round] / 1024) << "," << data_sizes[round] << ","
                 << std::fixed << std::setprecision(3) << detailed_times.round_times[round][iter];

            // 写入每个对等方的发送和接收时间
            for (int peer = 0; peer < log_n; peer++)
            {
                file << "," << std::fixed << std::setprecision(3) << detailed_times.send_times[round][iter][peer]
                     << "," << std::fixed << std::setprecision(3) << detailed_times.recv_times[round][iter][peer];
            }

            file << "," << party_id << "," << num_parties << std::endl;
        }
    }

    file.close();
    std::cout << "Detailed results written to: " << filename << std::endl;
}

void ShareBenchmarkTwoRounds::run_two_rounds_test(const std::vector<size_t> &data_sizes,
                                                  const std::string &output_csv_1, const std::string &output_csv_2)
{
    std::vector<std::pair<size_t, double>> results;

    std::cout << "\n=== Two Rounds EMP Share Benchmark ===" << std::endl;
    std::cout << "Party: " << party_id << ", Total Parties: " << num_parties << std::endl;
    std::cout << std::string(50, '=') << std::endl;

    // 第一轮测试
    std::cout << "Round 1 - Data Size: " << data_sizes[0] << " bytes ("
              << (data_sizes[0] / 1024) << " KB)" << std::endl;
    benchmark_round(data_sizes[0], 0, round_count);

    // 计算第一轮的平均时间
    double avg_time1 = 0.0;
    for (auto time : detailed_times.round_times[0])
    {
        avg_time1 += time;
    }
    avg_time1 /= detailed_times.round_times[0].size();
    results.push_back({data_sizes[0], avg_time1});
    std::cout << "Average Time: " << std::fixed << std::setprecision(3) << avg_time1 << " ms" << std::endl;

    // 第二轮测试
    std::cout << "Round 2 - Data Size: " << data_sizes[1] << " bytes ("
              << (data_sizes[1] / 1024) << " KB)" << std::endl;
    benchmark_round(data_sizes[1], 1, round_count);

    // 计算第二轮的平均时间
    double avg_time2 = 0.0;
    for (auto time : detailed_times.round_times[1])
    {
        avg_time2 += time;
    }
    avg_time2 /= detailed_times.round_times[1].size();
    results.push_back({data_sizes[1], avg_time2});
    std::cout << "Average Time: " << std::fixed << std::setprecision(3) << avg_time2 << " ms" << std::endl;

    std::cout << std::string(50, '=') << std::endl;

    // 写入原始CSV文件（保持兼容性）
    write_connection_to_csv(results, output_csv_2);

    // 写入详细时间CSV文件
    write_detailed_times_to_csv(data_sizes, output_csv_1);
}

// 读取配置文件的辅助函数
bool read_config(const std::string &filename, int &num_parties,
                 std::vector<std::string> &ips, std::vector<size_t> &data_sizes_kb)
{
    std::ifstream file(filename);
    if (!file.is_open())
    {
        std::cerr << "Cannot open config file: " << filename << std::endl;
        return false;
    }

    std::string line;

    // 读取参与方数量
    if (!std::getline(file, line))
    {
        std::cerr << "Failed to read number of parties" << std::endl;
        return false;
    }
    num_parties = std::stoi(line);

    // 读取IP地址
    for (int i = 0; i < num_parties; i++)
    {
        if (!std::getline(file, line))
        {
            std::cerr << "Failed to read IP address for party " << i << std::endl;
            return false;
        }
        ips.push_back(line);
    }

    // 读取数据大小（KB）
    if (!std::getline(file, line))
    {
        std::cerr << "Failed to read data sizes" << std::endl;
        return false;
    }

    std::istringstream iss(line);
    size_t size_kb;
    while (iss >> size_kb)
    {
        data_sizes_kb.push_back(size_kb);
    }

    if (data_sizes_kb.size() != 2)
    {
        std::cerr << "Expected exactly 2 data sizes in KB" << std::endl;
        return false;
    }

    return true;
}

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cout << "Usage: ./share_benchmark <party_id> <config_file> [network_mode]" << std::endl;
        std::cout << "Example: ./share_benchmark 0 config.txt lan" << std::endl;
        std::cout << "Example: ./share_benchmark 0 config.txt wan" << std::endl;
        return 1;
    }

    try
    {
        int party_id = std::stoi(argv[1]);
        std::string config_file = argv[2];
        std::string network_mode = argv[3];
        if (network_mode != "lan" && network_mode != "wan")
        {
            std::cerr << "警告: 网络模式应该是 'lan' 或 'wan'，使用默认值: " << network_mode << std::endl;
        }

        int num_parties = 0;
        std::vector<std::string> ips;
        std::vector<size_t> data_sizes_kb;

        if (!read_config(config_file, num_parties, ips, data_sizes_kb))
        {
            std::cerr << "Failed to read config file" << std::endl;
            return 1;
        }

        if (party_id < 0 || party_id >= num_parties)
        {
            std::cerr << "Invalid party ID. Must be between 0 and " << num_parties - 1 << std::endl;
            return 1;
        }

        std::cout << "Starting two-rounds benchmark as party " << party_id << std::endl;
        std::cout << "Number of parties: " << num_parties << std::endl;
        std::cout << "Network mode: " << network_mode << std::endl;
        std::cout << "Data sizes from config: " << data_sizes_kb[0] << " KB, "
                  << data_sizes_kb[1] << " KB" << std::endl;

        ShareBenchmarkTwoRounds benchmark(party_id, num_parties);

        // 设置网络连接
        int base_port = 8080;
        if (!benchmark.setup_connections(ips, base_port))
        {
            std::cerr << "Failed to setup network connections" << std::endl;
            return 1;
        }

        // 将KB转换为字节
        std::vector<size_t> data_sizes_bytes = {
            data_sizes_kb[0] * 1024,
            data_sizes_kb[1] * 1024};

        // 生成CSV文件名（包含party信息）
        std::stringstream csv_filename_1;
        csv_filename_1 << "benchmark_results_p" << num_parties
                       << "_id" << party_id
                       << "_" << network_mode
                       << ".csv";

        std::stringstream csv_filename_2;
        csv_filename_2 << "connection_p" << num_parties
                       << "_id" << party_id
                       << "_" << network_mode
                       << ".csv";

        // 运行两轮测试
        benchmark.run_two_rounds_test(data_sizes_bytes, csv_filename_1.str(), csv_filename_2.str());

        std::cout << "Two-rounds benchmark completed!" << std::endl;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}