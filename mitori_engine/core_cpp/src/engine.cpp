#include "../include/engine.hpp"

ArenaAllocator::ArenaAllocator(size_t capacity) : pool(capacity), offset(0) {
    pool.resize(capacity);
}

Order* ArenaAllocator::allocate() {
    if (offset >= pool.size()) {
        throw std::runtime_error("ArenaAllocator: Out of memory");
    }
    return &pool[offset++];
}

void ArenaAllocator::reset() {
    offset = 0;
}
