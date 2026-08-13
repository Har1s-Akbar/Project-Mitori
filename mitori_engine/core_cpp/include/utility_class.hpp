#pragma once 
#include <cstdint>

enum class Side:uint8_t {
    BUY = 0,
    SELL = 1
};

enum class Type:uint8_t{
    LIMIT = 0,
    MARKET = 1
};
