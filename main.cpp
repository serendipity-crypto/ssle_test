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

class ShareBenchmarkTwoRounds
{
private:
    int party_id;
    int num_parties;
    std::vector<emp::NetIO *> ios;
    std::vector<emp::NetIO *> io_servers;
    std::vector<std::vector<uint8_t>> recv_buffers; // 预分配的接收缓冲区

public:
    ShareBenchmarkTwoRounds(int party_id, int num_parties);
    ~ShareBenchmarkTwoRounds();

    // 网络设置
    bool setup_connections(const std::vector<std::string> &ips, int base_port);

    // 两轮测试函数
    void run_two_rounds_test(const std::vector<size_t> &data_sizes,
                             const std::string &output_csv = "benchmark_results.csv");

private:
    double benchmark_round(size_t data_size, int iterations = 5);
    void share_data(const std::vector<uint8_t> &data);
    void share_data_with_preallocated_buffers(const std::vector<uint8_t> &data);
    std::vector<uint8_t> generate_random_data(size_t size);
    void synchronize();
    void write_to_csv(const std::vector<std::pair<size_t, double>> &results,
                      const std::string &filename);
    void preallocate_buffers(size_t data_size);
};

ShareBenchmarkTwoRounds::ShareBenchmarkTwoRounds(int pid, int nparties)
    : party_id(pid), num_parties(nparties)
{
    ios.resize(num_parties, nullptr);
    io_servers.resize(num_parties, nullptr);
    recv_buffers.resize(num_parties);
}

ShareBenchmarkTwoRounds::~ShareBenchmarkTwoRounds()
{
    for (auto io : ios)
    {
        if (io)
            delete io;
    }
    for (auto io : io_servers)
    {
        if (io)
            delete io;
    }
}

bool ShareBenchmarkTwoRounds::setup_connections(const std::vector<std::string> &ips, int base_port)
{
    try
    {
        // 先启动服务器（监听连接）
        for (int i = 0; i < num_parties; i++)
        {
            if (i == party_id)
                continue;

            int port = base_port + party_id * 100 + i;
            io_servers[i] = new emp::NetIO(nullptr, port, true);
            std::cout << "Party " << party_id << " listening on port " << port << std::endl;
        }

        // 等待所有服务器启动
        std::this_thread::sleep_for(std::chrono::seconds(2));

        // 连接到其他参与方
        for (int i = 0; i < num_parties; i++)
        {
            if (i == party_id)
            {
                ios[i] = nullptr;
                continue;
            }

            int port = base_port + i * 100 + party_id;
            std::cout << "Party " << party_id << " connecting to " << ips[i]
                      << ":" << port << std::endl;

            ios[i] = new emp::NetIO(ips[i].c_str(), port);

            // 接受连接
            if (io_servers[i])
            {
                delete io_servers[i];
                io_servers[i] = nullptr;
            }
        }

        // 同步确保所有连接建立
        synchronize();
        return true;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Network setup error: " << e.what() << std::endl;
        return false;
    }
}

void ShareBenchmarkTwoRounds::synchronize()
{
    // 简单的同步协议
    for (int i = 0; i < num_parties; i++)
    {
        if (i == party_id)
            continue;

        char sync_msg = 'S';
        ios[i]->send_data(&sync_msg, 1);

        char ack;
        ios[i]->recv_data(&ack, 1);

        if (ack != 'A')
        {
            throw std::runtime_error("Synchronization failed");
        }
    }
}

std::vector<uint8_t> ShareBenchmarkTwoRounds::generate_random_data(size_t size)
{
    std::vector<uint8_t> data(size);
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 255);

    for (size_t i = 0; i < size; i++)
    {
        data[i] = static_cast<uint8_t>(dis(gen));
    }
    return data;
}

void ShareBenchmarkTwoRounds::preallocate_buffers(size_t data_size)
{
    // 为每个连接预分配接收缓冲区
    for (int i = 0; i < num_parties; i++)
    {
        if (i == party_id)
            continue;
        recv_buffers[i].resize(data_size);
    }
}

void ShareBenchmarkTwoRounds::share_data_with_preallocated_buffers(const std::vector<uint8_t> &data)
{
    // 直接发送数据给所有其他参与方
    for (int i = 0; i < num_parties; i++)
    {
        if (i == party_id)
            continue;
        ios[i]->send_data(data.data(), data.size());
    }

    // 从所有其他参与方接收数据到预分配的缓冲区
    for (int i = 0; i < num_parties; i++)
    {
        if (i == party_id)
            continue;
        ios[i]->recv_data(recv_buffers[i].data(), data.size());
    }
}

double ShareBenchmarkTwoRounds::benchmark_round(size_t data_size, int iterations)
{
    auto data = generate_random_data(data_size);

    // 预分配缓冲区
    preallocate_buffers(data_size);

    // 预热
    share_data_with_preallocated_buffers(generate_random_data(data_size));

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < iterations; i++)
    {
        share_data_with_preallocated_buffers(data);
    }

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);

    return duration.count() / (iterations * 1000.0); // 返回每次操作的毫秒数
}

void ShareBenchmarkTwoRounds::write_to_csv(const std::vector<std::pair<size_t, double>> &results,
                                           const std::string &filename)
{
    std::ofstream file(filename);
    if (!file.is_open())
    {
        std::cerr << "Failed to open CSV file: " << filename << std::endl;
        return;
    }

    // 写入CSV头部
    file << "Round,DataSize_KB,DataSize_Bytes,Time_ms,PartyID,NumParties" << std::endl;

    // 写入数据
    for (size_t i = 0; i < results.size(); i++)
    {
        file << (i + 1) << ","
             << (results[i].first / 1024) << ","
             << results[i].first << ","
             << std::fixed << std::setprecision(3) << results[i].second << ","
             << party_id << ","
             << num_parties << std::endl;
    }

    file.close();
    std::cout << "Results written to: " << filename << std::endl;
}

void ShareBenchmarkTwoRounds::run_two_rounds_test(const std::vector<size_t> &data_sizes,
                                                  const std::string &output_csv)
{
    if (data_sizes.size() != 2)
    {
        std::cerr << "Error: Exactly 2 data sizes required" << std::endl;
        return;
    }

    std::vector<std::pair<size_t, double>> results;

    std::cout << "\n=== Two Rounds EMP Share Benchmark ===" << std::endl;
    std::cout << "Party: " << party_id << ", Total Parties: " << num_parties << std::endl;
    std::cout << std::string(50, '=') << std::endl;

    // 第一轮测试
    std::cout << "Round 1 - Data Size: " << data_sizes[0] << " bytes ("
              << (data_sizes[0] / 1024) << " KB)" << std::endl;
    double time1 = benchmark_round(data_sizes[0], 5);
    results.push_back({data_sizes[0], time1});
    std::cout << "Time: " << std::fixed << std::setprecision(3) << time1 << " ms" << std::endl;

    // 第二轮测试
    std::cout << "Round 2 - Data Size: " << data_sizes[1] << " bytes ("
              << (data_sizes[1] / 1024) << " KB)" << std::endl;
    double time2 = benchmark_round(data_sizes[1], 5);
    results.push_back({data_sizes[1], time2});
    std::cout << "Time: " << std::fixed << std::setprecision(3) << time2 << " ms" << std::endl;

    std::cout << std::string(50, '=') << std::endl;

    // 写入CSV文件
    write_to_csv(results, output_csv);
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
        std::cout << "Usage: ./benchmark_two_rounds <party_id> <config_file> [network_mode]" << std::endl;
        std::cout << "Example: ./benchmark_two_rounds 0 config.txt lan" << std::endl;
        std::cout << "Example: ./benchmark_two_rounds 0 config.txt wan" << std::endl;
        return 1;
    }

    try
    {
        int party_id = std::stoi(argv[1]);
        std::string config_file = argv[2];
        std::string network_mode = "unknown";
        network_mode = argv[3];
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
        std::stringstream csv_filename;
        csv_filename << "benchmark_results_p" << num_parties 
                     << "_id" << party_id 
                     << "_" << network_mode 
                     << ".csv";

        // 运行两轮测试
        benchmark.run_two_rounds_test(data_sizes_bytes, csv_filename.str());

        std::cout << "Two-rounds benchmark completed!" << std::endl;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
