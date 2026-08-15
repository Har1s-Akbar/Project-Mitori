#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include "../include/engine.hpp"
#include "../include/utility_class.hpp"

namespace py = pybind11;

const uint64_t PRICE_PRECISION = 100000000;

PYBIND11_MODULE(mitori_engine_cpp, m){
    m.doc() = "Mitori Engine Python Bindings- C++ to python bridge";
    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL);
    
    py::enum_<Type>(m, "Type")
        .value("LIMIT", Type::LIMIT)
        .value("MARKET", Type::MARKET);
    py::class_<Trade>(m, "Trade")
        .def_readonly("ticker", &Trade::ticker)
        .def_property_readonly("quantity", [](const Trade& t) {
            return static_cast<double>(t.quantity) / PRICE_PRECISION;
        })
        .def_property_readonly("buyer_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id >> 64); })
        .def_property_readonly("buyer_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id); })
        .def_property_readonly("seller_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id >> 64); })
        .def_property_readonly("seller_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id); })
        
        .def_property_readonly("price_locked_by_user", [](const Trade& t) {
            return static_cast<double>(t.price_locked_by_user) / PRICE_PRECISION;
        })
        .def_property_readonly("price_settled_at", [](const Trade& t) {
            return static_cast<double>(t.price_setteled_at) / PRICE_PRECISION;
        });

    py::class_<OrderBook>(m,"OrderBook")
        .def(py::init<std::string>())
        .def("process_order", [](OrderBook & book,
                    uint64_t order_id_high , uint64_t order_id_low,
                    uint64_t order_owner_id_high, uint64_t order_owner_id_low,
                    Side side,
                    Type type,
                    bool is_canceled,
                    double price,
                    double number_of_shares,
                    std::optional<double> max_authorized_funds){
                        Order* order = ArenaAllocator::allocate();
                        
                        unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
                        unsigned __int128 full_owner_id = (static_cast<unsigned __int128>(order_owner_id_high) << 64) | order_owner_id_low;
                        
                        uint32_t current_meta_index = book.metadata_vault.size();
                        book.metadata_vault.push_back({full_order_id, full_owner_id});
                        
                        order->metadata_index = current_meta_index;
                        order->type = type;
                        order->side = side;
                        order->is_canceled = is_canceled;
                        
                        order->price = static_cast<uint64_t>(price * PRICE_PRECISION);
                        order->number_of_shares = static_cast<uint64_t>(number_of_shares * PRICE_PRECISION); 
                        
                        if (max_authorized_funds.has_value()) {
                            order->max_authorized_funds = static_cast<uint64_t>(max_authorized_funds.value() * PRICE_PRECISION);
                        } else {
                            order->max_authorized_funds = UINT64_MAX; 
                        }
                        return book.process_order(order);
        })
        .def("tombstone_delete", [](OrderBook& book, uint64_t order_id_high, uint64_t order_id_low) {
            unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
            book.tombstone_delete(full_order_id);
        })
        .def("get_current_bbo", [](OrderBook & book){
            auto bbo = book.get_current_bbo();
            std::unordered_map<std::string, double> scaled_bbo;
            scaled_bbo["best_ask_price"] = static_cast<double>(bbo["best_ask_price"]) / PRICE_PRECISION;
            scaled_bbo["best_bid_price"] = static_cast<double>(bbo["best_bid_price"]) / PRICE_PRECISION;
            return scaled_bbo;
        });
        
        m.def("reset_memory", &ArenaAllocator::reset, "Zero-latency allocator reset");
        m.def("cleanup_memory", &ArenaAllocator::cleanup, "Safely destroy memory slabs");
}