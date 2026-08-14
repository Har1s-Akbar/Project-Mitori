#include "../include/engine.hpp"

OrderBook::OrderBook(std::string ticker) {
    this->ticker = ticker;
    this->current_time = 0;
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

std::vector<Trade> OrderBook::process_order(Order* order){
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
        executed_trades = match_sell(order);
        if(order->number_of_shares > 0){
            asks.push(order);
            active_uuids[order->order_id] = order;
        }
    }
    }else if(order->type == Type::MARKET){
        if(order->side == Side::BUY){
            executed_trades = match_buy(order);
        }else{
            executed_trades = match_sell(order);
        }
    }
    return executed_trades;
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

        if(buy_order->type == Type::MARKET && buy_order->max_authorized_funds > 0){
            uint64_t total_cost = trade_quantity * trade_price;
            if(total_spent + total_cost > buy_order->max_authorized_funds){
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
    return executed_trades;
}
std::vector<Trade> OrderBook::match_sell(Order* sell_order) {
    std::vector<Trade> executed_trades;

    while (!bids.empty() && sell_order->number_of_shares > 0) {
        Order* best_bid = bids.top();
        
        if (canceled_uuids.find(best_bid->order_id) != canceled_uuids.end()) {
            bids.pop();
            canceled_uuids.erase(best_bid->order_id);
            continue;
        }

        if (sell_order->type == Type::LIMIT && sell_order->price > best_bid->price) {
            break; 
        }

        uint64_t trade_shares = std::min(sell_order->number_of_shares, best_bid->number_of_shares);
        uint64_t trade_price = best_bid->price; 

       if (sell_order->type == Type::LIMIT) {
            if (sell_order->date_time < best_bid->date_time) {
                trade_price = sell_order->price;
            }
        }

        sell_order->number_of_shares -= trade_shares;
        best_bid->number_of_shares -= trade_shares;

        Trade t;
        t.ticker = this->ticker;
        t.quantity = trade_shares; 
        t.price_setteled_at = trade_price;
        t.price_locked_by_user = (sell_order->type == Type::LIMIT) ? sell_order->price : 0;
        t.buyer_id = best_bid->order_owner_id; 
        t.seller_id = sell_order->order_owner_id;
        t.date_time = sell_order->date_time;
        t.order_id = sell_order->order_id;
        
        executed_trades.push_back(t);

        if (best_bid->number_of_shares == 0) {
            bids.pop();
            active_uuids.erase(best_bid->order_id);
        }
    }

    return executed_trades;
}

Order* OrderBook::find_order_by_id(const std::string& order_id) {
    auto it = active_uuids.find(order_id);
    if (it != active_uuids.end()) {
        return it->second;
    }
    return nullptr; 
}

Order* OrderBook::tombstone_delete(const std::string& order_id) {
    Order* order = find_order_by_id(order_id);
    if (order) {
        order->is_canceled = true;
        canceled_uuids.insert(order_id);
        active_uuids.erase(order_id);
    }
    return order;
}

std::unordered_map<std::string, uint64_t> OrderBook::get_current_bbo() {
    uint64_t best_ask = 0;
    uint64_t best_bid = 0;

    while (!asks.empty()) {
        Order* top_ask = asks.top();        
        if (canceled_uuids.find(top_ask->order_id) == canceled_uuids.end()) {
            best_ask = top_ask->price;
            break;
        } else {
            asks.pop();
            canceled_uuids.erase(top_ask->order_id);
        }
    }
    while (!bids.empty()) {
        Order* top_bid = bids.top();
        
        if (canceled_uuids.find(top_bid->order_id) == canceled_uuids.end()) {
            best_bid = top_bid->price;
            break;
        } else {
            bids.pop();
            canceled_uuids.erase(top_bid->order_id);
        }
    }
    std::unordered_map<std::string, uint64_t> bbo;
    bbo["best_ask_price"] = best_ask;
    bbo["best_bid_price"] = best_bid;
    
    return bbo;
}