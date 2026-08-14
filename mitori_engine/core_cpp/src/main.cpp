#include <iostream>
#include "../include/engine.hpp"

int main() {
    OrderBook book("APP");
    std::cout << "Engine initialized for " << book.ticker << "\n\n";

    Order* sell_order = ArenaAllocator::allocate();
    sell_order->order_id = "sell_123";
    sell_order->order_owner_id = "user_A";
    sell_order->type = Type::LIMIT;
    sell_order->side = Side::SELL;
    sell_order->price = 50000;
    sell_order->number_of_shares = 10;
    sell_order->date_time = 1000;

    std::cout << "Pushing Maker Sell: 10 shares @ $50,000\n";
    std::vector<Trade> trades1 = book.process_order(sell_order);
    
    Order* buy_order = ArenaAllocator::allocate();
    buy_order->order_id = "buy_456";
    buy_order->order_owner_id = "user_B";
    buy_order->type = Type::LIMIT;
    buy_order->side = Side::BUY;
    buy_order->price = 51000; 
    buy_order->number_of_shares = 5;
    buy_order->date_time = 1001;
    buy_order->max_authorized_funds = 300000; 

    std::cout << "Pushing Taker Buy: 5 shares @ $51,000\n";
    std::vector<Trade> trades2 = book.process_order(buy_order);

    if (!trades2.empty()) {
        std::cout << "\n--- TRADE EXECUTED ---\n";
        for (const auto& t : trades2) {
            std::cout << "Quantity: " << t.quantity << "\n";
            std::cout << "Settled Price: $" << t.price_setteled_at << "\n";
            std::cout << "Buyer ID: " << t.buyer_id << " | Seller ID: " << t.seller_id << "\n";
        }
    } else {
        std::cout << "\nNo trades executed.\n";
    }

    auto bbo = book.get_current_bbo();
    std::cout << "\nCurrent BBO -> Ask: $" << bbo["best_ask_price"] 
              << " | Bid: $" << bbo["best_bid_price"] << "\n";

    ArenaAllocator::cleanup();
    std::cout << "Memory slabs safely destroyed.\n";

    return 0;
}