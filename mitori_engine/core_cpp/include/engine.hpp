#pragma once
#include <vector>
#include <queue>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <string>
#include <mutex>

#include "utility_class.hpp"

class ArenaAllocator {
private:
    inline static const size_t SLAB_SIZE = 10000; // 10,000 orders per chunk
    inline static std::vector<Order*> slabs;      // Pointers to our allocated chunk memory
    
    inline static size_t current_slab = 0;
    inline static size_t current_offset = 0;
    inline static std::mutex allocation_mutex;
public:
    static uint32_t allocate_index() {
        std::lock_guard<std::mutex> lock(allocation_mutex);

        if (slabs.empty()) {
            slabs.push_back(new Order[SLAB_SIZE]);
        }

        if (current_offset >= SLAB_SIZE) {
            current_slab++;
            current_offset = 0;

            if (current_slab >= slabs.size()) {
                slabs.push_back(new Order[SLAB_SIZE]);
            }
        }

        uint32_t index = (current_slab * SLAB_SIZE) + current_offset;
        current_offset++;
        return index;
    }

    static Order* get_order(uint32_t index) {
        size_t slab = index / SLAB_SIZE;
        size_t offset = index % SLAB_SIZE;
        return &slabs[slab][offset];
    }

    static void reset() {
        std::lock_guard<std::mutex> lock(allocation_mutex);
        current_slab = 0;
        current_offset = 0;
    }

    static void cleanup() {
        std::lock_guard<std::mutex> lock(allocation_mutex);
        for (Order* slab : slabs) {
            delete[] slab;
        }
        slabs.clear();
        current_slab = 0;
        current_offset = 0;
    }
};

struct BidComparator {
    bool operator()(const uint32_t a_index, const uint32_t b_index) const;
};

struct AskComparator {
    bool operator()(const uint32_t a_index, const uint32_t b_index) const;
};

struct Int128Hash {
    std::size_t operator()(const unsigned __int128& k) const {
        uint64_t high = static_cast<uint64_t>(k >> 64);
        uint64_t low = static_cast<uint64_t>(k);
        // XOR the high and low bits together for a fast, zero-allocation hash
        return std::hash<uint64_t>()(high) ^ (std::hash<uint64_t>()(low) << 1);
    }
};

class OrderBook {
private:
    std::priority_queue<uint32_t, std::vector<uint32_t>, BidComparator> bids;
    std::priority_queue<uint32_t, std::vector<uint32_t>, AskComparator> asks;
    uint64_t current_time;

    std::unordered_map<unsigned __int128, Order*, Int128Hash> active_orders;
    std::unordered_set<unsigned __int128, Int128Hash> canceled_orders;

public:
    explicit OrderBook(std::string ticker);
    
    std::vector<OrderMetadata> metadata_vault; 
    
    std::vector<Trade> match_buy(uint32_t buy_order_idx);
    std::vector<Trade> match_sell(uint32_t sell_order_idx);

    std::string ticker; 
    
    std::vector<Trade> process_order(uint32_t order_idx);
    
    Order* tombstone_delete(unsigned __int128 order_id);
    Order* find_order_by_id(unsigned __int128 order_id);    
    std::unordered_map<std::string, uint64_t> get_current_bbo();
    
    uint64_t get_book_depth();

    void reset_engine();
};