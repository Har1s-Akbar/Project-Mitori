#pragma once 
#include <cstdint>
#include <string>

enum class Side:uint8_t {
    BUY = 0,
    SELL = 1
};

enum class Type:uint8_t{
    LIMIT = 0,
    MARKET = 1
};

struct alignas(64) Order{
    std::string ticker;
    std::string order_id;
    uint64_t price;
    uint64_t number_ofshares;
    uint64_t date_time;
    Side side;
    Type type;
    bool is_canceled;
    std::string order_owner_id;
    uint64_t max_auuthorized_funds;
};

struct Trade{
    std::string ticker;
    uint64_t price;
    uint64_t price_setteled_at;
    uint64_t price_locked_by_user;
    std::string buyer_id;
    std::string seller_id;
    uint64_t date_time;
    std::string order_id;
};