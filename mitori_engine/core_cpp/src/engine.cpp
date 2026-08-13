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
    
    std::vector<Trade> executed_trades;
    if(order->type == Type::LIMIT){
        if(order->side == Side::BUY){
            executed_trades = match_buy(order);
            if(order->number_of_shares > 0){
                bids.push(order);
                active_uuids[order->order_id] = order;
            }
    }else{
        match_sell(order);
        if(order->number_of_shares > 0){
            asks.push(order);
            active_uuids[order->order_id] = order;
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

std::vector<Trade> OrderBook::match_buy(Order* buy_order){
    std::vector<Trade> executed_trades;

    uint64_t total_spent = 0;
    while(!asks.empty() && buy_order->number_of_shares>0){
        Order* best_ask = asks.top();

        if(canceled_uuids.find(best_ask->order_id) != canceled_uuids.end()){
            asks.pop();
            canceled_uuids.erase(best_ask->order_id);
            continue;
        }
        if(buy_order->type == Type::LIMIT && buy_order->price < best_ask->price){
            break;
        }

        uint64_t trade_quantity = std::min(buy_order->number_of_shares, best_ask->number_of_shares);
        uint64_t trade_price = best_ask->price;

        if(buy_order->type == Type::LIMIT){
            if(buy_order->date_time < best_ask->date_time){
                trade_price = buy_order->price;
            }
        }

        if(buy_order->type == Type::MARKET && buy_order->max_auuthorized_funds > 0){
            uint64_t total_cost = trade_quantity * trade_price;
            if(total_spent + total_cost > buy_order->max_auuthorized_funds){
                break;
            }
            total_spent += total_cost;
        }
        buy_order->number_of_shares -= trade_quantity;
        best_ask->number_of_shares -= trade_quantity;

        Trade t;
        t.ticker = this->ticker;
        t.quantity = trade_quantity; 
        t.price_setteled_at = trade_price; 
        t.price_locked_by_user = (buy_order->type == Type::LIMIT) ? buy_order->price : 0;
        t.buyer_id = buy_order->order_owner_id;
        t.seller_id = best_ask->order_owner_id;
        
        executed_trades.push_back(t);

        if (best_ask->number_of_shares == 0) {
            asks.pop();
            active_uuids.erase(best_ask->order_id);
        }
    }
}