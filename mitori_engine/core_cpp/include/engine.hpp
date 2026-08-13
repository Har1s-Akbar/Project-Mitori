#pragma once
#include <vector>
#include <queue>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

#include "utility_class.hpp"

class ArenaAllocator {
private:
    std::vector<Order> pool;
    size_t offset;

public:
    explicit ArenaAllocator(size_t capacity);
    
    Order* allocate();
    
    void reset();
};

struct BidComparator {
    bool operator()(const Order* a, const Order* b) const;
};

struct AskComparator {
    bool operator()(const Order* a, const Order* b) const;
};

class OrderBook {
private:
    std::string ticker;
    std::priority_queue<Order*, std::vector<Order*>, BidComparator> bids;
    std::priority_queue<Order*, std::vector<Order*>, AskComparator> asks;
    uint64_t current_time;

    std::unordered_map<std::string,Order*> active_uuids;
    std::unordered_set<std::string> canceled_uuids;

    std::vector<Trade> match_buy(Order* buy_order);
    std::vector<Trade> match_sell(Order* sell_order);

public:
    OrderBook(std::string ticker);

    void process_order(Order* order);
    
    void reset();
};