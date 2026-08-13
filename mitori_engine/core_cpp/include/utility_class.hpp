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
    std::string order_id;
    uint64_t price;
    uint64_t number_ofshares;
    uint64_t timestamp;
    Side side;
    Type type;
    bool is_canceled;
};