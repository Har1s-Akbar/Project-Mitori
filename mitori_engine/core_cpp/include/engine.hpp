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
    inline static const size_t SLAB_SIZE = 10000; // 10,000 orders per chunk
    inline static std::vector<Order*> slabs;      // Pointers to our allocated chunks
    
    inline static size_t current_slab = 0;
    inline static size_t current_offset = 0;

public:
    static Order* allocate() {
        if (slabs.empty()) {
            slabs.push_back(new Order[SLAB_SIZE]);
        }

        if (current_offset >= SLAB_SIZE) {
            current_slab++;
            current_offset = 0; // Reset offset for the new slab

            if (current_slab >= slabs.size()) {
                slabs.push_back(new Order[SLAB_SIZE]);
            }
        }

        return &slabs[current_slab][current_offset++];
    }

    static void reset() {
        current_slab = 0;
        current_offset = 0;
    }

    static void cleanup() {
        for (Order* slab : slabs) {
            delete[] slab;
        }
        slabs.clear();
        current_slab = 0;
        current_offset = 0;
    }
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

    std::unordered_map<std::string,Order*> active_uuids;
    std::unordered_set<std::string> canceled_uuids;

public:
    explicit OrderBook(std::string ticker);

    
    std::vector<Trade> match_buy(Order* buy_order);
    std::vector<Trade> match_sell(Order* sell_order);

    std::string ticker;
    std::vector<Trade> process_order(Order* order);
    Order* tombstone_delete(const std::string& order_uuid);
    Order* find_order_by_id(const std::string& order_uuid);    
    std::unordered_map<std::string, uint64_t> get_current_bbo();
    
    void reset();
};