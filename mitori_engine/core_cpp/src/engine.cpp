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
        return a->date_time > b->date_time;
    }
    return a->price < b->price; 
}
bool AskComparator::operator()(const Order* a , const Order* b)const{
    if(a-> price == b->price){
        return a->date_time > b->date_time;
    }
    return a->price > b->price;
}

void OrderBook::reset(){
    current_time = 0;

    bids = std::priority_queue<Order*, std::vector<Order*>, BidComparator>();
    asks = std::priority_queue<Order*, std::vector<Order*>, AskComparator>();
}

void OrderBook::process_order(Order* order){
    order->date_time = current_time++;
    order->is_canceled = false;
    
    if(order->type == Type::LIMIT){
        if(order->side == Side::BUY){
            match_buy(order);
            if(order->number_ofshares > 0){
                bids.push(order);
            }
    }else{
        match_sell(order);
        if(order->number_ofshares > 0){
            asks.push(order);
        }
    }
    }else if(order->type == Type::MARKET){
        if(order->side == Side::BUY){
            match_buy(order);
        }else{
            match_sell(order);
        }
    }
}