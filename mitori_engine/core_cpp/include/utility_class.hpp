#pragma once 
#include <cstdint>
#include <string>

enum class Side : uint8_t {
    BUY = 0,
    SELL = 1
};

enum class Type : uint8_t {
    LIMIT = 0,
    MARKET = 1
};

struct OrderMetadata {
    unsigned __int128 order_id;
    unsigned __int128 owner_id;
};

struct Order {
    uint64_t price;                 // 8 bytes
    uint64_t number_of_shares;      // 8 bytes 
    uint64_t date_time;             // 8 bytes
    uint64_t max_authorized_funds;  // 8 bytes
    
    uint32_t metadata_index;        // 4 bytes (This links to the Vault!)
    
    Side side;                      // 1 byte
    Type type;                      // 1 byte
    bool is_canceled;               // 1 byte
    
    // Total: 39 bytes. 
    // C++ adds 1 invisible byte of padding at the end to make it an even 40 bytes.
};

struct Trade {
    std::string ticker;
    uint64_t quantity;
    uint64_t price_setteled_at;
    uint64_t price_locked_by_user;
    unsigned __int128 buyer_id;  
    unsigned __int128 seller_id;
    // uint64_t date_time;
    // std::string order_id;
    // these date_time and order_id will be configured in the pybind11 implementation phase
};