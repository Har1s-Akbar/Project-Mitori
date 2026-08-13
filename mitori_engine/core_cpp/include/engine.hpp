#pragma once
#include <vector>
#include <queue>
#include <cstdint>
#include <stdexcept>
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
    std::priority_queue<Order*, std::vector<Order*>, BidComparator> bids;
    std::priority_queue<Order*, std::vector<Order*>, AskComparator> asks;
    uint64_t current_time;

    void match_buy(Order* buy_order);
    void match_sell(Order* sell_order);

public:
    OrderBook();

    void process_order(Order* order);
    
    void reset();
};