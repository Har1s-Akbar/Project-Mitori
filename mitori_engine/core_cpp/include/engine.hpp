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
