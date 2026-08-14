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



struct alignas(128) Order{
    std::string order_id; //32 byte
    uint64_t price; // 8 byte
    uint64_t number_of_shares; // 8 byte 
    uint64_t date_time; // 8 byte
    Side side; // 1 byte
    Type type; // 1 byte
    bool is_canceled; // 1 byte
    std::string order_owner_id; // 32 byte
    uint64_t max_authorized_funds; // 1 byte
};
// total size of Order struct is 99 bytes, compiler injects 29 bytes , which is a multiple of 64 bytes. This ensures that each Order instance is aligned to a cache line boundary, which can improve performance when accessing Order instances in memory.

struct Trade{
    std::string ticker;
    uint64_t quantity;
    uint64_t price_setteled_at;
    uint64_t price_locked_by_user;
    std::string buyer_id;
    std::string seller_id;
    uint64_t date_time;
    std::string order_id;
};