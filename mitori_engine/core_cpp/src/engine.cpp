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

bool BidComparator::operator()(const Order* a, const Order* b) const {
    if(a->price == b->price){
        return a->timestamp > b->timestamp;
    }
    return a->price < b->price; 
}
bool AskComparator::operator()(const Order* a , const Order* b)const{
    if(a-> price == b->price){
        return a->timestamp > b->timestamp;
    }
    return a->price > b->price;
}