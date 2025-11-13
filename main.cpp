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

const size_t round_count = 3;

class ShareBenchmarkTwoRounds
{
private:
    int party_id;
    int num_parties;
    int log_n;
    std::vector<emp::NetIO *> ios;
    std::vector<uint8_t> recv_buffers; // 预分配的接收缓冲区
    std::mt19937 rng_engine;

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
    void share_data(size_t size);
    void generate_random_data(size_t size);
    void write_to_csv(const std::vector<std::pair<size_t, double>> &results,
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

void ShareBenchmarkTwoRounds::share_data(size_t data_size)
{
    int mask = 1;
    size_t current_offset = party_id * data_size;
    size_t current_size = data_size;

    for (int i = 0; i < log_n; i++)
    {
        int peer_id = party_id ^ mask;

        if (party_id < peer_id)
        {
            // std::cout << "Party " << party_id << " send to Party " << peer_id << std::endl;
            ios[i]->send_data(recv_buffers.data() + current_offset, current_size);
            ios[i]->flush();
            // std::cout << "Party " << party_id << " recv from Party " << peer_id << std::endl;
            ios[i]->recv_data(recv_buffers.data() + current_offset + current_size, current_size);
        }
        else
        {
            // std::cout << "Party " << party_id << " recv from Party " << peer_id << std::endl;
            ios[i]->recv_data(recv_buffers.data() + current_offset - current_size, current_size);
            // std::cout << "Party " << party_id << " send to Party " << peer_id << std::endl;
            ios[i]->send_data(recv_buffers.data() + current_offset, current_size);
            ios[i]->flush();
            current_offset -= current_size;
        }

        mask <<= 1;
        current_size *= 2;
    }
}

double ShareBenchmarkTwoRounds::benchmark_round(size_t data_size, int iterations)
{
    // 预分配缓冲区
    preallocate_buffers(data_size);

    generate_random_data(data_size);

    // 预热
    share_data(data_size);

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < iterations; i++)
    {
        share_data(data_size);
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

    std::vector<std::pair<size_t, double>> results;

    std::cout << "\n=== Two Rounds EMP Share Benchmark ===" << std::endl;
    std::cout << "Party: " << party_id << ", Total Parties: " << num_parties << std::endl;
    std::cout << std::string(50, '=') << std::endl;

    // 第一轮测试
    std::cout << "Round 1 - Data Size: " << data_sizes[0] << " bytes ("
              << (data_sizes[0] / 1024) << " KB)" << std::endl;
    double time1 = benchmark_round(data_sizes[0], round_count);
    results.push_back({data_sizes[0], time1});
    std::cout << "Time: " << std::fixed << std::setprecision(3) << time1 << " ms" << std::endl;

    // 第二轮测试
    std::cout << "Round 2 - Data Size: " << data_sizes[1] << " bytes ("
              << (data_sizes[1] / 1024) << " KB)" << std::endl;
    double time2 = benchmark_round(data_sizes[1], round_count);
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
        std::cout << "Usage: ./share_benchmark <party_id> <config_file> [network_mode]" << std::endl;
        std::cout << "Example: ./share_benchmark 0 config.txt lan" << std::endl;
        std::cout << "Example: ./share_benchmark 0 config.txt wan" << std::endl;
        // std::cout << "argc:" << argc << std::endl;
        // for (int i = 0; i < argc; i++)
        // {
        //     std::cout << argv[i] << std::endl;
        // }
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
