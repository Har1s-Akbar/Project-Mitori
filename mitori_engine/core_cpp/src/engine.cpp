#include "../include/engine.hpp"

const uint64_t PRICE_PRECISION = 100000000;

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
    if(a->price == b->price){
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
    
    unsigned __int128 current_order_id = metadata_vault[order->metadata_index].order_id;
    
    std::vector<Trade> executed_trades;
    if(order->type == Type::LIMIT){
        if(order->side == Side::BUY){
            executed_trades = match_buy(order);
            if(order->number_of_shares > 0){
                bids.push(order);
                active_orders[current_order_id] = order;
            }
        } else {
            executed_trades = match_sell(order);
            if(order->number_of_shares > 0){
                asks.push(order);
                active_orders[current_order_id] = order;
            }
        }
    } else if(order->type == Type::MARKET){
        if(order->side == Side::BUY){
            executed_trades = match_buy(order);
        } else {
            executed_trades = match_sell(order);
        }
    }
    return executed_trades;
}
std::vector<Trade> OrderBook::match_buy(Order* buy_order){
    std::vector<Trade> executed_trades;
    uint64_t total_spent = 0;
    
    while(!asks.empty() && buy_order->number_of_shares > 0){
        Order* best_ask = asks.top();
        if(best_ask->is_canceled){
            asks.pop();
            unsigned __int128 best_ask_id = metadata_vault[best_ask->metadata_index].order_id;
            canceled_orders.erase(best_ask_id);
            continue;
        }
        if(buy_order->type == Type::LIMIT && buy_order->price < best_ask->price){
            break;
        }
        uint64_t trade_quantity = std::min(buy_order->number_of_shares, best_ask->number_of_shares);
        uint64_t trade_price = best_ask->price;

        if (trade_price == 0) {
            if (buy_order->type == Type::LIMIT) {
                trade_price = buy_order->price; 
            } else {
                break;
            }
        } else if (buy_order->type == Type::LIMIT) {
            if(buy_order->date_time < best_ask->date_time) {
                trade_price = buy_order->price;
            }
        }

        if(buy_order->type == Type::MARKET && buy_order->max_authorized_funds != UINT64_MAX){
            unsigned __int128 scaled_cost = (unsigned __int128)trade_quantity * (unsigned __int128)trade_price;
            uint64_t total_cost = static_cast<uint64_t>(scaled_cost / PRICE_PRECISION);

            if(total_cost % PRICE_PRECISION != 0){
                total_cost += 1;
            }

            if(total_spent + total_cost > buy_order->max_authorized_funds) {
                uint64_t remaining_funds = buy_order->max_authorized_funds - total_spent;

                unsigned __int128 affordable_shares = ((unsigned __int128)remaining_funds * PRICE_PRECISION) / trade_price;
                trade_quantity = static_cast<uint64_t>(affordable_shares);
                
                if (trade_quantity == 0) {
                    break;
                }
                
                scaled_cost = (unsigned __int128)trade_quantity * (unsigned __int128)trade_price;
                total_cost = static_cast<uint64_t>(scaled_cost / PRICE_PRECISION);
                if(total_cost % PRICE_PRECISION != 0) total_cost += 1;
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
        
        t.buyer_id = metadata_vault[buy_order->metadata_index].owner_id;
        t.seller_id = metadata_vault[best_ask->metadata_index].owner_id;

        executed_trades.push_back(t);

        if (best_ask->number_of_shares == 0) {
            asks.pop();
            unsigned __int128 best_ask_id = metadata_vault[best_ask->metadata_index].order_id;
            active_orders.erase(best_ask_id);
        }
    }
    return executed_trades;
}
std::vector<Trade> OrderBook::match_sell(Order* sell_order) {
    std::vector<Trade> executed_trades;

    while (!bids.empty() && sell_order->number_of_shares > 0) {
        Order* best_bid = bids.top();
        
        if (best_bid->is_canceled) {
            bids.pop();
            unsigned __int128 best_bid_id = metadata_vault[best_bid->metadata_index].order_id;
            canceled_orders.erase(best_bid_id);
            continue;
        }

        if (sell_order->type == Type::LIMIT && sell_order->price > best_bid->price) {
            break; 
        }

        uint64_t trade_shares = std::min(sell_order->number_of_shares, best_bid->number_of_shares);
        uint64_t trade_price = best_bid->price; 

        if (trade_price == 0) {
            if (sell_order->type == Type::LIMIT) {
                trade_price = sell_order->price;
            } else {
                break;
            }
        } else if (sell_order->type == Type::LIMIT) {
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
        
        t.buyer_id = metadata_vault[best_bid->metadata_index].owner_id; 
        t.seller_id = metadata_vault[sell_order->metadata_index].owner_id;
        
        executed_trades.push_back(t);

        if (best_bid->number_of_shares == 0) {
            bids.pop();
            unsigned __int128 best_bid_id = metadata_vault[best_bid->metadata_index].order_id;
            active_orders.erase(best_bid_id);
        }
    }

    return executed_trades;
}

std::unordered_map<std::string, uint64_t> OrderBook::get_current_bbo() {
    uint64_t best_ask = 0;
    uint64_t best_bid = 0;

    while (!asks.empty()) {
        Order* top_ask = asks.top();        
        
        if (!top_ask->is_canceled) {
            best_ask = top_ask->price;
            break;
        } else {
            asks.pop();
            unsigned __int128 top_ask_id = metadata_vault[top_ask->metadata_index].order_id;
            canceled_orders.erase(top_ask_id);
        }
    }
    
    while (!bids.empty()) {
        Order* top_bid = bids.top();
        
        if (!top_bid->is_canceled) {
            best_bid = top_bid->price;
            break;
        } else {
            bids.pop();
            unsigned __int128 top_bid_id = metadata_vault[top_bid->metadata_index].order_id;
            canceled_orders.erase(top_bid_id);
        }
    }
    
    std::unordered_map<std::string, uint64_t> bbo;
    bbo["best_ask_price"] = best_ask;
    bbo["best_bid_price"] = best_bid;
    
    return bbo;
}

Order* OrderBook::find_order_by_id(unsigned __int128 order_id) {
    auto it = active_orders.find(order_id);
    if (it != active_orders.end()) {
        return it->second;
    }
    return nullptr; 
}

Order* OrderBook::tombstone_delete(unsigned __int128 order_id) {
    Order* order = find_order_by_id(order_id);
    if (order) {
        order->is_canceled = true;
        canceled_orders.insert(order_id);
        active_orders.erase(order_id);
    }
    return order;
}
